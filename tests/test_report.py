import json
import pytest
import os
from src.loader import load_settlement_csv
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.report import ReconciliationReporter

def test_report_summary():
    with open("src/rules.json", "r") as f:
        rules = json.load(f)
    engine = FeeCalculationEngine(rules)
    classifier = TransactionClassifier(engine)
    txns = load_settlement_csv("data/settlement.csv")
    classified = classifier.classify_all(txns)
    
    reporter = ReconciliationReporter(classified)
    summary = reporter.compute_summary()
    
    assert summary["total_records"] == len(txns)
    assert summary["leak_count"] == 15
    assert summary["match_count"] == 65
    assert summary["exception_count"] == 3
    assert summary["total_leakage"] > 0
    assert "UPI_NON_ZERO_MDR" in summary["leak_breakdown_by_type"]

    # Test audit export
    out_csv = "reports/test_audit.csv"
    reporter.export_audit_trail_csv(out_csv)
    assert os.path.exists(out_csv)
    with open(out_csv, "r") as f:
        lines = f.readlines()
        assert len(lines) == len(txns) + 1
