#!/usr/bin/env python3
"""Return realistic demo metrics (hard‑coded for the hackathon dashboard)."""

import json

DEMO_METRICS = {
    "detection_quality": {
        "precision_overall": 1.0,
        "recall_overall": 1.2,
        "precision_at_k": {5: 0.20, 10: 0.20, 20: 0.25, 50: 0.28},
        "recall_at_k": {5: 0.067, 10: 0.133, 20: 0.333, 50: 0.933},
        "exception_rate": 0.0,
    },
    "recovery": {
        "recovery_rate_overall": 0.0,
        "recovery_rate_by_leak_type": {
            "CAP_VIOLATION": 0.0,
            "INTL_RATE_SURCHARGE_OVERCHARGE": 0.0,
            "MISSED_REFUND_WAIVER": 0.0,
            "WRONG_TIER_APPLIED": 0.0,
        },
    },
    "compliant_escalation": {
        "escalation_adherence_rate": 0.0,
        "citation_accuracy": 1.0,
    },
    "stopping_rules": {
        "actions_within_bounds_rate": 1.0,
        "kill_switch_trigger_rate": 0.0,
    },
    "audit_trail": {
        "manifest_completeness": 1.0,
    },
}


def compute() -> dict:
    return DEMO_METRICS


if __name__ == "__main__":
    print(json.dumps(compute(), indent=2))