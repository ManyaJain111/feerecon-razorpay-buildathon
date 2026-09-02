import pytest
import os
import json
from src.rule_extractor import extract_rules, validate_rules_schema

def test_extract_rules():
    contract_path = "data/contract.md"
    assert os.path.exists(contract_path)
    rules = extract_rules(contract_path, output_path="src/rules.json")
    assert validate_rules_schema(rules) is True
    assert "UPI" in rules["rules"]["payment_methods"]
    assert rules["rules"]["payment_methods"]["UPI"]["rate_pct"] == 0.0
    assert rules["rules"]["payment_methods"]["DOMESTIC_CARD"]["type"] == "tiered_volume"
    assert len(rules["rules"]["payment_methods"]["DOMESTIC_CARD"]["tiers"]) == 3
    assert rules["rules"]["refund_policy"]["waiver_window_hours"] == 24.0
    assert rules["rules"]["statutory_tax"]["gst_rate_pct"] == 18.0
