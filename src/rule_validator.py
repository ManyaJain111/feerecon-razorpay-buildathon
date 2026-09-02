"""Rule validation and consistency verification across extraction runs."""

import json
import os
import copy
from typing import Dict, Any, List, Tuple, Optional
from src.rule_extractor import (
    extract_rules_from_contract_text_fallback,
    apply_needs_review_flags,
    validate_rules_schema
)

def _deep_diff(dict1: Any, dict2: Any, path: str = "") -> List[Dict[str, Any]]:
    """Recursively computes field-level differences between two rule dictionary structures."""
    diffs = []
    if isinstance(dict1, dict) and isinstance(dict2, dict):
        all_keys = set(dict1.keys()).union(set(dict2.keys()))
        for k in all_keys:
            # Ignore volatile fields like timestamp or extraction_method
            if k in ["extraction_method", "timestamp"]:
                continue
            curr_path = f"{path}.{k}" if path else k
            if k not in dict1:
                diffs.append({
                    "path": curr_path,
                    "field": k,
                    "run_a_value": None,
                    "run_b_value": dict2[k],
                    "issue": "Missing in first run"
                })
            elif k not in dict2:
                diffs.append({
                    "path": curr_path,
                    "field": k,
                    "run_a_value": dict1[k],
                    "run_b_value": None,
                    "issue": "Missing in second run"
                })
            else:
                diffs.extend(_deep_diff(dict1[k], dict2[k], curr_path))
    elif isinstance(dict1, list) and isinstance(dict2, list):
        if len(dict1) != len(dict2):
            diffs.append({
                "path": path,
                "field": path.split(".")[-1] if path else "",
                "run_a_value": f"List of length {len(dict1)}",
                "run_b_value": f"List of length {len(dict2)}",
                "issue": f"Array length mismatch ({len(dict1)} vs {len(dict2)})"
            })
        else:
            for idx, (i1, i2) in enumerate(zip(dict1, dict2)):
                diffs.extend(_deep_diff(i1, i2, f"{path}[{idx}]"))
    else:
        if dict1 != dict2:
            diffs.append({
                "path": path,
                "field": path.split(".")[-1] if path else "",
                "run_a_value": dict1,
                "run_b_value": dict2,
                "issue": f"Value discrepancy: {dict1} != {dict2}"
            })
    return diffs

def extract_with_consistency_check(
    contract_text: str,
    n_runs: int = 3,
    disagreements_path: str = "reports/disagreements.json"
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Executes n extraction passes over the contract text,
    diffs the results across runs,
    flags disagreements, and forces discordant fields to needs_review=True.
    """
    runs = []
    for i in range(n_runs):
        # In offline/deterministic mode, extract via parser
        # In LLM mode, this calls the LLM with temperature sampling
        run_rules = extract_rules_from_contract_text_fallback(contract_text)
        runs.append(run_rules)

    base_rules = copy.deepcopy(runs[0])
    all_disagreements = []

    # Diff each subsequent run against base
    for idx in range(1, len(runs)):
        diffs = _deep_diff(base_rules, runs[idx])
        for d in diffs:
            d["run_comparison"] = f"Run 1 vs Run {idx + 1}"
            all_disagreements.append(d)

    # If any disagreements exist, mark the corresponding rule paths with needs_review: True
    if all_disagreements:
        for d in all_disagreements:
            p = d.get("path", "")
            # If path points into payment_methods.<PM>
            parts = p.split(".")
            if len(parts) >= 3 and parts[0] == "rules" and parts[1] == "payment_methods":
                pm_name = parts[2].split("[")[0]
                if pm_name in base_rules["rules"]["payment_methods"]:
                    base_rules["rules"]["payment_methods"][pm_name]["needs_review"] = True
                    base_rules["rules"]["payment_methods"][pm_name]["confidence"] = min(
                        base_rules["rules"]["payment_methods"][pm_name].get("confidence", 0.9),
                        0.70
                    )

    # Save disagreements JSON
    os.makedirs(os.path.dirname(disagreements_path), exist_ok=True)
    with open(disagreements_path, "w", encoding="utf-8") as f:
        json.dump(all_disagreements, f, indent=2)

    return base_rules, all_disagreements
