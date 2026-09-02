import pytest
from src.classifier import TransactionClassifier
from src.engine import FeeCalculationEngine
from src.audit_store import AuditStore
from src.trend_analyzer import TrendAnalyzer

def test_risk_severity_and_confidence():
    dummy_rules = {
        "rules": {
            "payment_methods": {
                "UPI": {
                    "type": "flat",
                    "rate_pct": 0.0,
                    "fixed_fee": 0.0,
                    "confidence": 0.70, # < 0.85 -> LOW confidence
                    "needs_review": True
                },
                "NETBANKING": {
                    "type": "flat_with_cap",
                    "rate_pct": 1.8,
                    "fee_cap": 20.0,
                    "confidence": 0.98,
                    "needs_review": False
                }
            }
        }
    }
    engine = FeeCalculationEngine(dummy_rules)
    classifier = TransactionClassifier(engine)

    # UPI leak with low rule confidence -> confidence should be LOW
    upi_leak = {
        "txn_id": "T_UPI_1",
        "payment_method": "UPI",
        "amount": 500.0,
        "fee_billed": 10.0,
        "gst_billed": 1.80,
        "total_billed": 11.80
    }
    res_upi = classifier.classify_transaction(upi_leak)
    assert res_upi["status"] == "LEAK"
    assert res_upi["confidence"] == "LOW"

    # Netbanking large leak (>1000 delta) -> severity should be CRITICAL
    nb_leak = {
        "txn_id": "T_NB_1",
        "payment_method": "NETBANKING",
        "amount": 100000.0,
        "fee_billed": 1800.0,
        "gst_billed": 324.0,
        "total_billed": 2124.0
    }
    res_nb = classifier.classify_transaction(nb_leak)
    assert res_nb["status"] == "LEAK"
    assert res_nb["severity"] == "CRITICAL"
    assert res_nb["confidence"] == "HIGH"

def test_trend_analyzer_detection(tmp_path):
    db_path = str(tmp_path / "test_trends.db")
    store = AuditStore(db_path=db_path)

    # Insert recurring leaks across batches
    records_b1 = [
        {"txn_id": "T1", "status": "LEAK", "is_leak": True, "leak_type": "WRONG_TIER_APPLIED", "amount": 1000, "delta": 50.0, "payment_method": "DOMESTIC_CARD"},
        {"txn_id": "T2", "status": "LEAK", "is_leak": True, "leak_type": "WRONG_TIER_APPLIED", "amount": 1000, "delta": 60.0, "payment_method": "DOMESTIC_CARD"},
        {"txn_id": "T3", "status": "LEAK", "is_leak": True, "leak_type": "WRONG_TIER_APPLIED", "amount": 1000, "delta": 70.0, "payment_method": "DOMESTIC_CARD"},
    ]
    store.save_records(records_b1, batch_id="BATCH_JAN")

    analyzer = TrendAnalyzer(store)
    alerts = analyzer.analyze_recurring_patterns(min_recurring_count=1)
    assert len(alerts) >= 1
    assert alerts[0]["leak_type"] == "WRONG_TIER_APPLIED"
    assert "renegotiation" in alerts[0]["recommendation"].lower()
