"""Dispute claim draft generator in markdown format with cited contract clauses."""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

DEFAULT_CLAUSE_CITATIONS = {
    "UPI_NON_ZERO_MDR": "Schedule B, Section 1.1: Unified Payments Interface (UPI) - 0.00% Zero MDR mandate.",
    "WRONG_TIER_APPLIED": "Schedule B, Section 1.2: Domestic Debit and Credit Cards - Volume-tiered bracket rates.",
    "CAP_VIOLATION": "Schedule B, Section 1.3: Netbanking - Flat 1.80% MDR subject to maximum ₹20.00 fee cap.",
    "MISSED_REFUND_WAIVER": "Schedule B, Section 2.2: 24-Hour Express Refund Fee Waiver (100% waived / ₹0.00).",
    "INTL_RATE_SURCHARGE_OVERCHARGE": "Schedule B, Section 1.4: International Cards - Contracted MDR and fixed surcharge.",
    "WALLET_OVERCHARGE": "Schedule B, Section 1.5: Digital Wallets & BNPL Schedule - Flat 2.10% MDR.",
    "FEE_OVERCHARGE": "Schedule B: General Service Fee Schedule."
}

def generate_dispute_draft(
    leak_records: List[Dict[str, Any]],
    contract_info: Optional[Dict[str, Any]] = None,
    batch_id: str = "BATCH_001",
    output_dir: str = "reports"
) -> str:
    """
    Generates a dispute claim markdown document for overbilled transactions.
    Filters for actionable leaks, itemizes discrepancies, and cites contract clauses.
    Writes output to reports/dispute_draft_{batch_id}.md and returns markdown string.
    """
    contract_id = (contract_info or {}).get("contract_id", "RZP-COMM-2025-88492")
    merchant_name = (contract_info or {}).get("merchant_name", "Zenith Retail Technologies Private Limited")
    
    leaks = [r for r in leak_records if r.get("status") == "LEAK" or r.get("is_leak")]
    total_claim_amount = sum(float(l.get("delta", 0.0)) for l in leaks)

    lines = [
        f"# PAYMENT GATEWAY FEE DISPUTE CLAIM NOTICE",
        f"**Date:** {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        f"**Batch Reference:** {batch_id}",
        f"**Agreement Reference:** {contract_id}",
        f"**Merchant Name:** {merchant_name}",
        f"**Total Disputed Claim Amount:** ₹{total_claim_amount:,.2f}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        f"Pursuant to the terms of Merchant Service Agreement **{contract_id}**, the Merchant has conducted an automated fee reconciliation audit for batch **{batch_id}**. "
        f"A total of **{len(leaks)} overcharged transactions** were detected, resulting in an aggregate fee leakage of **₹{total_claim_amount:,.2f}**.",
        "We formally request a credit note / adjustment refund to the merchant settlement balance for the full disputed sum.",
        "",
        "## 2. Itemized Breakdown & Contract Clause Citations",
        "",
        "| Transaction ID | Method | Txn Amount | Billed Fee | Expected Fee | Claim Amount | Severity | Cited Contract Clause |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for l in leaks:
        txn_id = l.get("txn_id", "N/A")
        pm = l.get("payment_method", "N/A")
        amt = float(l.get("amount", 0.0))
        billed = float(l.get("billed_total", 0.0))
        exp = float(l.get("expected_total", 0.0))
        delta = float(l.get("delta", 0.0))
        severity = l.get("severity", "MODERATE")
        lt = l.get("leak_type", "FEE_OVERCHARGE")
        
        clause = l.get("source_span") or DEFAULT_CLAUSE_CITATIONS.get(lt, "Schedule B: Pricing Schedule")
        short_clause = (clause[:60] + "...") if len(clause) > 60 else clause

        lines.append(
            f"| `{txn_id}` | {pm} | ₹{amt:,.2f} | ₹{billed:.2f} | ₹{exp:.2f} | **₹{delta:.2f}** | `{severity}` | {short_clause} |"
        )

    lines.extend([
        "",
        "## 3. Discrepancy Diagnostics & Evidence",
        ""
    ])

    for l in leaks:
        lines.append(f"### Claim Item: `{l.get('txn_id')}` ({l.get('leak_type')})")
        lines.append(f"- **Discrepancy:** {l.get('reason')}")
        lines.append(f"- **Reconciliation Formula:** `{l.get('formula_audit', 'N/A')}`")
        if l.get("source_span"):
            lines.append(f"- **Contract Provision:** > *\"{l.get('source_span')}\"*")
        lines.append("")

    lines.extend([
        "## 4. Required Next Steps",
        "1. Acknowledge receipt of this dispute claim within 48 business hours.",
        "2. Issue a formal credit adjustment of **₹" + f"{total_claim_amount:,.2f}" + "** in the subsequent settlement payout cycle.",
        "3. Correct the automated gateway billing rating rules to prevent recurring leakage.",
        "",
        "---",
        f"**Submitted by:** Automated Finance Controller on behalf of {merchant_name}"
    ])

    draft_md = "\n".join(lines)

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"dispute_draft_{batch_id}.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(draft_md)

    return draft_md
