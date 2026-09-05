"""Reconciliation report generator, terminal formatting, and CSV export."""

import json
import csv
import os
from typing import List, Dict, Any, Optional
from src.audit_store import AuditStore
from src.trend_analyzer import TrendAnalyzer
from src.dispute_generator import generate_dispute_draft

class ReconciliationReporter:
    def __init__(
        self,
        classified_records: List[Dict[str, Any]],
        batch_id: str = "BATCH_001",
        rule_version: str = "1.0",
        audit_store: Optional[AuditStore] = None
    ):
        self.records = classified_records
        self.batch_id = batch_id
        self.rule_version = rule_version
        self.audit_store = audit_store or AuditStore()
        self.trend_analyzer = TrendAnalyzer(self.audit_store)

    def sync_to_audit_store(self) -> int:
        """Persists classified records into SQLite audit store with idempotency deduplication."""
        return self.audit_store.save_records(
            self.records,
            batch_id=self.batch_id,
            rule_version=self.rule_version
        )

    def compute_summary(self) -> Dict[str, Any]:
        total_records = len(self.records)
        total_gmv = sum(r["amount"] for r in self.records)
        
        matches = [r for r in self.records if r["status"] == "MATCH"]
        leaks = [r for r in self.records if r["status"] == "LEAK"]
        exceptions = [r for r in self.records if r["status"] == "EXCEPTION"]
        undercharges = [r for r in self.records if r["status"] == "UNDERCHARGE"]

        total_billed = sum(r["billed_total"] for r in self.records if r["billed_total"] is not None)
        total_expected = sum(r["expected_total"] for r in self.records if r["expected_total"] is not None)
        total_leakage = sum(r["delta"] for r in leaks if r["delta"] is not None)
        
        # Leakage by severity tier
        severity_breakdown = {"CRITICAL": {"count": 0, "total_leakage": 0.0},
                              "MODERATE": {"count": 0, "total_leakage": 0.0},
                              "MINOR": {"count": 0, "total_leakage": 0.0}}
        for l in leaks:
            sev = l.get("severity", "MINOR")
            if sev in severity_breakdown:
                severity_breakdown[sev]["count"] += 1
                severity_breakdown[sev]["total_leakage"] = round(severity_breakdown[sev]["total_leakage"] + l["delta"], 2)

        # Leakage by leak_type
        leak_by_type = {}
        for l in leaks:
            lt = l["leak_type"]
            if lt not in leak_by_type:
                leak_by_type[lt] = {"count": 0, "total_leakage": 0.0}
            leak_by_type[lt]["count"] += 1
            leak_by_type[lt]["total_leakage"] = round(leak_by_type[lt]["total_leakage"] + l["delta"], 2)

        # Leakage by payment method
        leak_by_pm = {}
        for l in leaks:
            pm = l["payment_method"]
            if pm not in leak_by_pm:
                leak_by_pm[pm] = {"count": 0, "total_leakage": 0.0}
            leak_by_pm[pm]["count"] += 1
            leak_by_pm[pm]["total_leakage"] = round(leak_by_pm[pm]["total_leakage"] + l["delta"], 2)

        # Dispute KPIs from audit store
        dispute_kpis = self.audit_store.get_dispute_kpis()
        
        # Trend alerts
        trend_alerts = self.trend_analyzer.analyze_recurring_patterns()

        summary = {
            "batch_id": self.batch_id,
            "rule_version": self.rule_version,
            "total_records": total_records,
            "total_gmv": round(total_gmv, 2),
            "total_billed": round(total_billed, 2),
            "total_expected": round(total_expected, 2),
            "total_leakage": round(total_leakage, 2),
            "match_count": len(matches),
            "match_rate_pct": round((len(matches) / total_records) * 100, 2) if total_records else 0.0,
            "leak_count": len(leaks),
            "leak_rate_pct": round((len(leaks) / total_records) * 100, 2) if total_records else 0.0,
            "exception_count": len(exceptions),
            "exception_rate_pct": round((len(exceptions) / total_records) * 100, 2) if total_records else 0.0,
            "undercharge_count": len(undercharges),
            "severity_breakdown": severity_breakdown,
            "leak_breakdown_by_type": leak_by_type,
            "leak_breakdown_by_payment_method": leak_by_pm,
            "dispute_kpis": dispute_kpis,
            "trend_alerts": trend_alerts,
            "exceptions": [
                {
                    "txn_id": e["txn_id"],
                    "payment_method": e["payment_method"],
                    "amount": e["amount"],
                    "reason": e["reason"]
                }
                for e in exceptions
            ]
        }
        return summary

    def export_audit_trail_csv(self, output_path: str = "reports/audit_trail.csv"):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fieldnames = [
            "txn_id", "status", "payment_method", "amount",
            "billed_fee", "billed_gst", "billed_total",
            "expected_fee", "expected_gst", "expected_total",
            "delta", "severity", "match_confidence", "leak_type", "reason", "formula_audit"
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.records:
                row_dict = {
                    "txn_id": r["txn_id"],
                    "status": r["status"],
                    "payment_method": r["payment_method"],
                    "amount": f"{r['amount']:.2f}",
                    "billed_fee": f"{r['billed_fee']:.2f}" if r.get("billed_fee") is not None else "",
                    "billed_gst": f"{r['billed_gst']:.2f}" if r.get("billed_gst") is not None else "",
                    "billed_total": f"{r['billed_total']:.2f}" if r.get("billed_total") is not None else "",
                    "expected_fee": f"{r['expected_fee']:.2f}" if r.get("expected_fee") is not None else "",
                    "expected_gst": f"{r['expected_gst']:.2f}" if r.get("expected_gst") is not None else "",
                    "expected_total": f"{r['expected_total']:.2f}" if r.get("expected_total") is not None else "",
                    "delta": f"{r['delta']:.2f}" if r.get("delta") is not None else "",
                    "severity": r.get("severity", "NONE"),
                    "match_confidence": r.get("match_confidence", r.get("confidence", "HIGH")),
                    "leak_type": r["leak_type"],
                    "reason": r["reason"],
                    "formula_audit": r["formula_audit"]
                }
                writer.writerow(row_dict)

    def print_terminal_report(self):
        summary = self.compute_summary()
        sep = "=" * 70
        print("\n" + sep)
        print("          RAZORPAY FEE LEAKAGE DETECTOR: AUDIT SUMMARY          ")
        print(sep)
        print(f"Batch ID / Rule Version      : {summary['batch_id']} | v{summary['rule_version']}")
        print(f"Total Transactions Processed : {summary['total_records']}")
        print(f"Total GMV Volume Processed   : ₹{summary['total_gmv']:,.2f}")
        print(f"Total Gateway Fees Billed    : ₹{summary['total_billed']:,.2f}")
        print(f"Total Expected Contract Fees : ₹{summary['total_expected']:,.2f}")
        print(f"TOTAL DETECTED FEE LEAKAGE   : ₹{summary['total_leakage']:,.2f}")
        print("-" * 70)
        print(f"Clean Matches                : {summary['match_count']} ({summary['match_rate_pct']}%)")
        print(f"Fee Leaks (Overcharges)      : {summary['leak_count']} ({summary['leak_rate_pct']}%)")
        print(f"Exceptions (Needs Review)    : {summary['exception_count']} ({summary['exception_rate_pct']}%)")
        print("-" * 70)
        print("SEVERITY & MATERIALITY TIERS:")
        for sev, d in summary["severity_breakdown"].items():
            print(f"  • {sev:<12}: {d['count']:2d} txns | ₹{d['total_leakage']:>8.2f}")
        print("-" * 70)
        print("LEAKAGE BREAKDOWN BY TYPE:")
        for lt, data in summary["leak_breakdown_by_type"].items():
            print(f"  • {lt:<32}: {data['count']:2d} txns | ₹{data['total_leakage']:>8.2f}")
        print("-" * 70)
        print("DISPUTE & RECOVERY STATUS:")
        kpis = summary["dispute_kpis"]
        print(f"  • Total Detected Leakage   : ₹{kpis['total_detected_leakage']:,.2f}")
        print(f"  • Total Recovered Leakage  : ₹{kpis['total_recovered_leakage']:,.2f} ({kpis['recovery_rate_pct']}%)")
        print(f"  • Dispute Claims Resolved  : {kpis['resolved_disputes']}")
        
        if summary.get("trend_alerts"):
            print("-" * 70)
            print("CROSS-RUN TREND & RECURRING PATTERN ALERTS:")
            for alert in summary["trend_alerts"]:
                print(f"  • [{alert['alert_level']}] {alert['message']}")
                print(f"    -> {alert['recommendation']}")

        if summary["exceptions"]:
            print("-" * 70)
            print("UNRESOLVED CONTRACT EXCEPTIONS:")
            for exc in summary["exceptions"]:
                print(f"  • [{exc['txn_id']}] {exc['payment_method']} (₹{exc['amount']:,.2f}): {exc['reason']}")
        print(sep + "\n")
