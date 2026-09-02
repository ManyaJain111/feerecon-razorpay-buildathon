import json
import pytest
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.loader import load_settlement_csv

@pytest.fixture
def classifier():
    with open("src/rules.json", "r") as f:
        rules = json.load(f)
    engine = FeeCalculationEngine(rules)
    return TransactionClassifier(engine)

def test_classify_match(classifier):
    clean_txn = {
        "txn_id": "M_1",
        "payment_method": "UPI",
        "amount": 1000.0,
        "monthly_volume_to_date": 50000.0,
        "is_refund": False,
        "is_instant_settlement": False,
        "fee_billed": 0.0,
        "gst_billed": 0.0,
        "total_billed": 0.0
    }
    res = classifier.classify_transaction(clean_txn)
    assert res["status"] == "MATCH"
    assert res["is_leak"] is False
    assert res["delta"] == 0.0

def test_classify_leak(classifier):
    leak_txn = {
        "txn_id": "L_1",
        "payment_method": "UPI",
        "amount": 1000.0,
        "monthly_volume_to_date": 50000.0,
        "is_refund": False,
        "is_instant_settlement": False,
        "fee_billed": 5.0,
        "gst_billed": 0.90,
        "total_billed": 5.90
    }
    res = classifier.classify_transaction(leak_txn)
    assert res["status"] == "LEAK"
    assert res["is_leak"] is True
    assert res["delta"] == 5.90
    assert res["leak_type"] == "UPI_NON_ZERO_MDR"

def test_classify_dataset(classifier):
    txns = load_settlement_csv("data/settlement.csv")
    results = classifier.classify_all(txns)
    assert len(results) == len(txns)
    leaks = [r for r in results if r["status"] == "LEAK"]
    matches = [r for r in results if r["status"] == "MATCH"]
    exceptions = [r for r in results if r["status"] == "EXCEPTION"]
    assert len(leaks) == 15
    assert len(matches) == 65
    assert len(exceptions) == 3
