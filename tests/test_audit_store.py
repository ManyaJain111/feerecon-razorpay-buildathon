import pytest
import os
from src.audit_store import AuditStore

def test_audit_store_crud_and_idempotency(tmp_path):
    db_path = str(tmp_path / "test_audit.db")
    store = AuditStore(db_path=db_path)

    records = [
        {
            "txn_id": "TXN_001",
            "status": "LEAK",
            "is_leak": True,
            "payment_method": "UPI",
            "amount": 1000.0,
            "expected_fee": 0.0,
            "billed_fee": 5.0,
            "expected_total": 0.0,
            "billed_total": 5.90,
            "delta": 5.90,
            "leak_type": "UPI_NON_ZERO_MDR",
            "severity": "MINOR",
            "match_confidence": "HIGH",
            "reason": "UPI charged fee"
        },
        {
            "txn_id": "TXN_002",
            "status": "MATCH",
            "is_leak": False,
            "payment_method": "DOMESTIC_CARD",
            "amount": 1000.0,
            "expected_fee": 20.0,
            "billed_fee": 20.0,
            "expected_total": 23.60,
            "billed_total": 23.60,
            "delta": 0.0,
            "leak_type": "NONE",
            "severity": "NONE",
            "match_confidence": "HIGH",
            "reason": "Match"
        }
    ]

    # First write
    saved = store.save_records(records, batch_id="B1", rule_version="1.0")
    assert saved == 2

    # Query leaks
    leaks = store.query_leaks()
    assert len(leaks) == 1
    assert leaks[0]["txn_id"] == "TXN_001"
    assert leaks[0]["leak_amount"] == 5.90

    # Idempotent write (duplicate write should not double count)
    saved2 = store.save_records(records, batch_id="B1", rule_version="1.0")
    assert saved2 == 2
    leaks_after = store.query_leaks()
    assert len(leaks_after) == 1

def test_dispute_status_tracking(tmp_path):
    db_path = str(tmp_path / "test_disputes.db")
    store = AuditStore(db_path=db_path)

    records = [
        {
            "txn_id": "TXN_DISP_01",
            "status": "LEAK",
            "is_leak": True,
            "payment_method": "NETBANKING",
            "amount": 5000.0,
            "expected_fee": 20.0,
            "billed_fee": 90.0,
            "expected_total": 23.60,
            "billed_total": 106.20,
            "delta": 82.60,
            "leak_type": "CAP_VIOLATION",
            "severity": "MODERATE",
            "match_confidence": "HIGH",
            "reason": "Netbanking cap ignored"
        }
    ]
    store.save_records(records, batch_id="B_DISP")

    # Initial KPIs
    kpi1 = store.get_dispute_kpis()
    assert kpi1["total_detected_leakage"] == 82.60
    assert kpi1["total_recovered_leakage"] == 0.0
    assert kpi1["recovery_rate_pct"] == 0.0

    # Update status to resolved
    ok = store.update_dispute("TXN_DISP_01", status="resolved", resolution_amount=82.60)
    assert ok is True

    # Updated KPIs
    kpi2 = store.get_dispute_kpis()
    assert kpi2["total_recovered_leakage"] == 82.60
    assert kpi2["recovery_rate_pct"] == 100.0
    assert kpi2["resolved_disputes"] == 1
