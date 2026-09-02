"""Versioned rule registry supporting time-effective rulesets."""

import json
import os
import glob
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

RULES_DIR = "data/rules"
DEFAULT_RULES_PATH = "src/rules.json"

class RulesRegistry:
    def __init__(self, rules_dir: str = RULES_DIR, default_rules_path: Optional[str] = DEFAULT_RULES_PATH):
        self.rules_dir = rules_dir
        self.default_rules_path = default_rules_path
        os.makedirs(self.rules_dir, exist_ok=True)

    def list_rulesets(self) -> List[Dict[str, Any]]:
        """Returns metadata for all available versioned rulesets sorted by effective date."""
        files = glob.glob(os.path.join(self.rules_dir, "rules_v*.json"))
        rulesets = []
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rulesets.append({
                        "file_path": fpath,
                        "version": str(data.get("version", "1.0")),
                        "effective_date": str(data.get("effective_date", "2025-01-01")),
                        "contract_id": data.get("contract_id", ""),
                        "merchant_name": data.get("merchant_name", "")
                    })
            except Exception:
                continue
        # Sort by effective date ascending
        rulesets.sort(key=lambda x: x["effective_date"])
        return rulesets

    def save_ruleset(self, rules_data: Dict[str, Any], version: Optional[str] = None, effective_date: Optional[str] = None) -> str:
        """Saves a versioned ruleset file and updates default mirror if configured."""
        v = version or rules_data.get("version", "1.0")
        v_clean = str(v).replace(".", "_")
        eff = effective_date or rules_data.get("effective_date", "2025-01-01")
        filename = f"rules_v{v_clean}_{eff}.json"
        target_path = os.path.join(self.rules_dir, filename)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, indent=2)

        # Update default mirror only if default_rules_path is specified and target is not in a temporary test dir
        if self.default_rules_path and not str(self.rules_dir).startswith("/tmp") and "pytest" not in str(self.rules_dir):
            os.makedirs(os.path.dirname(self.default_rules_path), exist_ok=True)
            with open(self.default_rules_path, "w", encoding="utf-8") as f:
                json.dump(rules_data, f, indent=2)

        return target_path

    def get_active_ruleset(self, transaction_date: Optional[str] = None, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches active ruleset for a specific transaction date or version.
        If transaction_date is provided (e.g., '2025-01-15' or ISO string),
        finds the ruleset with effective_date <= transaction_date with latest effective date.
        """
        rulesets = self.list_rulesets()
        
        if not rulesets:
            if self.default_rules_path and os.path.exists(self.default_rules_path):
                with open(self.default_rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                from src.rule_extractor import extract_rules
                rules = extract_rules("data/contract.md", output_path=self.default_rules_path)
                self.save_ruleset(rules)
                return rules

        if version is not None:
            for rs in rulesets:
                if rs["version"] == str(version) or rs["version"].replace("_", ".") == str(version):
                    with open(rs["file_path"], "r", encoding="utf-8") as f:
                        return json.load(f)

        if not transaction_date:
            with open(rulesets[-1]["file_path"], "r", encoding="utf-8") as f:
                return json.load(f)

        txn_date_str = str(transaction_date).split("T")[0].split(" ")[0]
        
        active_rs = rulesets[0]
        for rs in rulesets:
            if rs["effective_date"] <= txn_date_str:
                active_rs = rs
            else:
                break

        with open(active_rs["file_path"], "r", encoding="utf-8") as f:
            return json.load(f)

# Module-level helper
_global_registry = RulesRegistry()

def get_active_ruleset(transaction_date: Optional[str] = None, version: Optional[str] = None) -> Dict[str, Any]:
    return _global_registry.get_active_ruleset(transaction_date, version)

def save_versioned_ruleset(rules_data: Dict[str, Any], version: Optional[str] = None, effective_date: Optional[str] = None) -> str:
    return _global_registry.save_ruleset(rules_data, version, effective_date)
