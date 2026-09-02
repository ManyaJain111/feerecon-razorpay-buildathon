import json
import pytest
from src.engine import FeeCalculationEngine

@pytest.fixture
def engine():
    with open("src/rules.json", "r") as f:
        rules = json.load(f)
    return FeeCalculationEngine(rules)

def test_upi_fee_zero(engine):
    txn = {
        "txn_id": "T1",
        "payment_method": "UPI",
        "amount": 5000.0,
        "monthly_volume_to_date": 100000.0,
        "is_refund": False,
        "is_instant_settlement": False
    }
    res = engine.compute_expected_fee(txn)
    assert res["status"] == "success"
    assert res["expected_fee"] == 0.0
    assert res["expected_gst"] == 0.0
    assert res["expected_total"] == 0.0

def test_card_tiered_rates(engine):
    # Tier 1 (<= 5L) -> 2.00%
    t1 = {"txn_id": "T1", "payment_method": "DOMESTIC_CARD", "amount": 1000.0, "monthly_volume_to_date": 300000.0}
    r1 = engine.compute_expected_fee(t1)
    assert r1["expected_fee"] == 20.0
    assert r1["expected_gst"] == 3.60
    assert r1["expected_total"] == 23.60

    # Tier 2 (5L - 20L) -> 1.75%
    t2 = {"txn_id": "T2", "payment_method": "DOMESTIC_CARD", "amount": 1000.0, "monthly_volume_to_date": 800000.0}
    r2 = engine.compute_expected_fee(t2)
    assert r2["expected_fee"] == 17.50
    assert r2["expected_gst"] == 3.15
    assert r2["expected_total"] == 20.65

    # Tier 3 (> 20L) -> 1.50%
    t3 = {"txn_id": "T3", "payment_method": "DOMESTIC_CARD", "amount": 1000.0, "monthly_volume_to_date": 2500000.0}
    r3 = engine.compute_expected_fee(t3)
    assert r3["expected_fee"] == 15.00
    assert r3["expected_gst"] == 2.70
    assert r3["expected_total"] == 17.70

def test_netbanking_cap(engine):
    # Below cap: 1.8% on 500 = 9.00
    nb1 = {"txn_id": "NB1", "payment_method": "NETBANKING", "amount": 500.0, "monthly_volume_to_date": 0}
    assert engine.compute_expected_fee(nb1)["expected_fee"] == 9.00

    # Above cap: 1.8% on 5000 = 90.00 -> capped at 20.00
    nb2 = {"txn_id": "NB2", "payment_method": "NETBANKING", "amount": 5000.0, "monthly_volume_to_date": 0}
    assert engine.compute_expected_fee(nb2)["expected_fee"] == 20.00

def test_refund_waiver(engine):
    # Under 24h -> fee waived (0.00)
    ref1 = {"txn_id": "R1", "payment_method": "DOMESTIC_CARD", "amount": 1000.0, "monthly_volume_to_date": 100000.0, "is_refund": True, "refund_hours_after_txn": 12.0}
    r1 = engine.compute_expected_fee(ref1)
    assert r1["breakdown"]["refund_fee"] == 0.0

    # Over 24h -> standard ₹5 fee
    ref2 = {"txn_id": "R2", "payment_method": "DOMESTIC_CARD", "amount": 1000.0, "monthly_volume_to_date": 100000.0, "is_refund": True, "refund_hours_after_txn": 30.0}
    r2 = engine.compute_expected_fee(ref2)
    assert r2["breakdown"]["refund_fee"] == 5.00

def test_unrecognized_payment_exception(engine):
    txn = {"txn_id": "EX1", "payment_method": "CRYPTO_PAY", "amount": 1000.0}
    res = engine.compute_expected_fee(txn)
    assert res["status"] == "exception"
