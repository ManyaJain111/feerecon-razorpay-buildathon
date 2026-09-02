import pytest
import os
import json
from src.rules_registry import RulesRegistry

def test_rules_registry_date_lookup(tmp_path):
    reg_dir = tmp_path / "rules"
    reg = RulesRegistry(rules_dir=str(reg_dir), default_rules_path=None)

    # Save rule version 1 (effective 2025-01-01)
    r1 = {
        "version": "1.0",
        "effective_date": "2025-01-01",
        "rules": {"payment_methods": {"UPI": {"rate_pct": 0.0}}}
    }
    reg.save_ruleset(r1, version="1.0", effective_date="2025-01-01")

    # Save rule version 2 (effective 2025-06-01)
    r2 = {
        "version": "2.0",
        "effective_date": "2025-06-01",
        "rules": {"payment_methods": {"UPI": {"rate_pct": 0.10}}}
    }
    reg.save_ruleset(r2, version="2.0", effective_date="2025-06-01")

    # Query before June 1
    active_jan = reg.get_active_ruleset(transaction_date="2025-03-15")
    assert active_jan["version"] == "1.0"
    assert active_jan["rules"]["payment_methods"]["UPI"]["rate_pct"] == 0.0

    # Query after June 1
    active_jul = reg.get_active_ruleset(transaction_date="2025-07-20")
    assert active_jul["version"] == "2.0"
    assert active_jul["rules"]["payment_methods"]["UPI"]["rate_pct"] == 0.10

    # Query by explicit version
    v1_explicit = reg.get_active_ruleset(version="1.0")
    assert v1_explicit["version"] == "1.0"
