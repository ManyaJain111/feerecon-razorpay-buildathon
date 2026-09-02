#!/usr/bin/env python3
"""CLI entrypoint for payment gateway fee reconciliation."""

import argparse
import os
import sys
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rule_extractor import extract_rules
from src.rule_validator import extract_with_consistency_check
from src.rules_registry import get_active_ruleset, save_versioned_ruleset, RulesRegistry
from src.adapters import get_gateway_adapter
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.report import ReconciliationReporter
from src.audit_store import AuditStore
from src.dispute_generator import generate_dispute_draft
from src.manifest import create_run_manifest
from src.pdf_processor import (
    extract_text_from_pdf,
    detect_pdf_document_type,
    extract_rules_from_pdf_text,
    parse_statement_from_pdf_text
)
from eval.evaluate import run_evaluation

def main():
    parser = argparse.ArgumentParser(
        description="Payment Fee Reconciliation & Audit CLI"
    )
    parser.add_argument(
        "--gateway",
        type=str,
        default="razorpay",
        help="Payment gateway adapter to use (e.g. razorpay, stripe, payu)"
    )
    parser.add_argument(
        "--contract",
        type=str,
        default="data/contract.md",
        help="Path to merchant pricing contract (Markdown, plain text, or PDF)"
    )
    parser.add_argument(
        "--settlement",
        type=str,
        default="data/settlement.csv",
        help="Path to settlement CSV or PDF file"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="Path to any PDF contract or statement to process directly"
    )
    parser.add_argument(
        "--generate-statements",
        action="store_true",
        help="Re-generate all account statement CSVs for sample PDFs in sample_pdf/"
    )
    parser.add_argument(
        "--rules",
        type=str,
        default="src/rules.json",
        help="Path to structured rules JSON cache"
    )
    parser.add_argument(
        "--rules-version",
        type=str,
        default=None,
        help="Specific ruleset version to pin from registry (e.g. '1.0')"
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Force re-extraction of rules from contract markdown with consistency checks"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force extraction even if disagreements exist across consistency runs"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/audit_trail.csv",
        help="Destination path for the CSV audit trail report"
    )
    parser.add_argument(
        "--generate-dispute",
        action="store_true",
        default=True,
        help="Auto-generate dispute claim draft markdown for detected leaks"
    )
    parser.add_argument(
        "--update-dispute",
        type=str,
        metavar="TXN_ID",
        help="Transaction ID to update dispute tracking status for"
    )
    parser.add_argument(
        "--dispute-status",
        type=str,
        choices=["none", "submitted", "acknowledged", "resolved", "rejected"],
        default="resolved",
        help="Dispute status to apply with --update-dispute"
    )
    parser.add_argument(
        "--resolution-amount",
        type=float,
        default=0.0,
        help="Recovered resolution amount to record with --update-dispute"
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run precision/recall benchmark against ground truth"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run high-volume parallel scaling benchmark"
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the Web UI dashboard on http://localhost:8000"
    )

    args = parser.parse_args()

    # Handle statement generation
    if args.generate_statements:
        from data.generate_sample_statements import generate_all
        print("[*] Generating account statement CSVs and rules JSON for sample PDFs...")
        generate_all()
        print("[OK] All sample statements and rulesets generated successfully.")
        return

    # Handle dispute tracking update directly
    if args.update_dispute:
        store = AuditStore()
        updated = store.update_dispute(
            txn_id=args.update_dispute,
            status=args.dispute_status,
            resolution_amount=args.resolution_amount
        )
        if updated:
            print(f"[OK] Successfully updated dispute for transaction '{args.update_dispute}': Status='{args.dispute_status}', Resolution Amount=₹{args.resolution_amount:.2f}")
            kpis = store.get_dispute_kpis()
            print(f"    Total Recovered: ₹{kpis['total_recovered_leakage']:,.2f} ({kpis['recovery_rate_pct']}% of detected leakage)")
        else:
            print(f"[!] Transaction ID '{args.update_dispute}' not found in audit store.")
        return

    if args.ui:
        import server
        print("\n" + "=" * 70)
        print("      STARTING WEB UI (FEE RECONCILIATION DASHBOARD)          ")
        print("      Available at: http://localhost:8000                        ")
        print("=" * 70 + "\n")
        server.start_server(8000)
        return

    print("\n" + "=" * 70)
    print(f"  PAYMENT FEE LEAKAGE DETECTOR [{args.gateway.upper()}]")
    print("=" * 70)

    # Handle single PDF processing mode
    if args.pdf:
        print(f"[*] Processing PDF document: {args.pdf}")
        pdf_text = extract_text_from_pdf(args.pdf)
        doc_type = detect_pdf_document_type(pdf_text, args.pdf)
        print(f"[OK] Document classified as: {doc_type.upper()}")
        if doc_type == "contract":
            rules_data = extract_rules_from_pdf_text(pdf_text, args.pdf)
            print(f"[OK] Extracted {len(rules_data['rules']['payment_methods'])} payment method fee schedules from PDF.")
            print(f"    Contract ID: {rules_data['contract_id']} | Merchant: {rules_data['merchant_name']}")
        else:
            records = parse_statement_from_pdf_text(pdf_text, args.pdf)
            print(f"[OK] Parsed {len(records)} transaction statement records from PDF.")
        return

    # 1. Gateway Adapter Dispatch
    adapter = get_gateway_adapter(args.gateway)

    # 2. Rule Extraction / Loading with Self-Consistency
    if args.extract or not os.path.exists(args.rules):
        print(f"[*] Extracting pricing rules with self-consistency validation (3 passes) from: {args.contract}...")
        with open(args.contract, "r", encoding="utf-8") as f:
            contract_text = f.read()
        
        rules_data, disagreements = extract_with_consistency_check(
            contract_text=contract_text,
            n_runs=3,
            disagreements_path="reports/disagreements.json"
        )
        
        if disagreements and not args.force:
            print(f"[!] WARNING: {len(disagreements)} disagreements detected across extraction runs!")
            print("[!] Disagreements logged to reports/disagreements.json. Use --force to proceed regardless.")
            sys.exit(1)
        elif disagreements:
            print(f"[!] Proceeding with --force despite {len(disagreements)} flagged extraction disagreements.")

        save_versioned_ruleset(rules_data, version=rules_data.get("version", "1.0"), effective_date=rules_data.get("effective_date", "2025-01-01"))
        print(f"[OK] Extracted rules verified and saved to registry and: {args.rules}")
    else:
        print(f"[*] Loading structured pricing rules (Version: {args.rules_version or 'active'}) from registry...")
        rules_data = get_active_ruleset(version=args.rules_version)

    rule_version = str(rules_data.get("version", "1.0"))

    # 3. Initialize Engine & Classifier
    engine = FeeCalculationEngine(rules_data)
    classifier = TransactionClassifier(engine)

    # 4. Load Settlement Records via Gateway Adapter
    print(f"[*] Ingesting settlement transactions from: {args.settlement} via {args.gateway.upper()} adapter...")
    records = adapter.parse_settlement(args.settlement)
    print(f"[OK] Ingested and validated {len(records)} transaction rows.")

    # 5. Deterministic Fee Reconciliation & Classification
    print("[*] Recomputing fees deterministically and classifying transactions...")
    classified_records = classifier.classify_all(records)

    # 6. Structured Audit Store Sync & Reporting
    batch_id = f"BATCH_{uuid.uuid4().hex[:8].upper()}"
    reporter = ReconciliationReporter(
        classified_records=classified_records,
        batch_id=batch_id,
        rule_version=rule_version
    )
    
    # Persist to SQLite with idempotency keys
    saved_rows = reporter.sync_to_audit_store()
    print(f"[OK] Persisted {saved_rows} transaction records into structured SQLite audit store.")

    summary = reporter.compute_summary()
    reporter.print_terminal_report()
    reporter.export_audit_trail_csv(args.output)
    print(f"[OK] Detailed row-by-row audit trail exported to: {args.output}")

    # 7. Auto-Generate Dispute Draft
    if args.generate_dispute and summary["leak_count"] > 0:
        dispute_draft_path = os.path.join("reports", f"dispute_draft_{batch_id}.md")
        generate_dispute_draft(
            leak_records=classified_records,
            contract_info=rules_data,
            batch_id=batch_id,
            output_dir="reports"
        )
        print(f"[OK] Auto-generated formal dispute claim draft: {dispute_draft_path}")

    # 8. Create Run Manifest (Observability)
    manifest_path = create_run_manifest(
        settlement_file=args.settlement,
        rules_version=rule_version,
        rules_file=args.rules,
        summary_metrics=summary,
        gateway=args.gateway
    )
    print(f"[OK] Immutable run manifest logged to: {manifest_path}")

    # 9. Evaluation / Benchmarking if requested
    if args.eval or args.benchmark:
        gt_path = "data/ground_truth.json"
        if os.path.exists(gt_path):
            print("\n[*] Running Benchmark Evaluation against ground truth...")
            run_evaluation(
                settlement_csv=args.settlement,
                rules_json=args.rules,
                ground_truth_json=gt_path,
                benchmark=args.benchmark
            )
        else:
            print(f"[!] Ground truth file not found at {gt_path}, skipping eval.")

if __name__ == "__main__":
    main()
