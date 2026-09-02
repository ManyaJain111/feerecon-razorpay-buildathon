import pytest
import os
import json
from src.rule_validator import extract_with_consistency_check, _deep_diff
from src.rule_extractor import perform_round_trip_validation, extract_rules

def test_extract_with_consistency_check():
    with open("data/contract.md", "r", encoding="utf-8") as f:
        text = f.read()

    rules, disagreements = extract_with_consistency_check(
        contract_text=text,
        n_runs=3,
        disagreements_path="reports/test_disagreements.json"
    )
    assert isinstance(rules, dict)
    assert len(disagreements) == 0
    assert os.path.exists("reports/test_disagreements.json")

def test_deep_diff_detects_mismatch():
    d1 = {"rules": {"payment_methods": {"UPI": {"rate_pct": 0.0}}}}
    d2 = {"rules": {"payment_methods": {"UPI": {"rate_pct": 0.5}}}}
    diffs = _deep_diff(d1, d2)
    assert len(diffs) == 1
    assert "rate_pct" in diffs[0]["path"]

def test_round_trip_semantic_validation():
    rules = extract_rules("data/contract.md", output_path=None)
    with open("data/contract.md", "r", encoding="utf-8") as f:
        contract_text = f.read()
    summary, discrepancies = perform_round_trip_validation(rules, contract_text, "reports/test_extraction_val.md")
    assert len(discrepancies) == 0
    assert os.path.exists("reports/test_extraction_val.md")
