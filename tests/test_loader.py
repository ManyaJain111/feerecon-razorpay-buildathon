import pytest
import os
from src.loader import load_settlement_csv

def test_load_settlement_csv():
    records = load_settlement_csv("data/settlement.csv")
    assert len(records) >= 60
    first = records[0]
    assert "txn_id" in first
    assert "payment_method" in first
    assert "amount" in first
    assert "total_billed" in first
    assert isinstance(first["amount"], float)
    assert isinstance(first["total_billed"], float)

def test_loader_missing_col(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("txn_id,amount\nTXN_1,100")
    with pytest.raises(ValueError, match="Missing required column"):
        load_settlement_csv(str(bad_csv))
