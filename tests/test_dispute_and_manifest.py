import pytest
import os
import json
from src.dispute_generator import generate_dispute_draft
from src.manifest import create_run_manifest, compute_file_sha256

def test_dispute_draft_generation(tmp_path):
    out_dir = str(tmp_path / "reports")
    leaks = [
        {
            "txn_id": "TXN_L1",
            "status": "LEAK",
            "is_leak": True,
            "payment_method": "UPI",
            "amount": 5000.0,
            "billed_total": 5.90,
            "expected_total": 0.0,
            "delta": 5.90,
            "severity": "MINOR",
            "leak_type": "UPI_NON_ZERO_MDR",
            "reason": "UPI charged fee",
            "source_span": "All UPI transactions shall be charged at 0.00% Zero MDR",
            "formula_audit": "UPI flat 0.0%"
        }
    ]

    draft_md = generate_dispute_draft(
        leak_records=leaks,
        contract_info={"contract_id": "TEST-123", "merchant_name": "Test Merchant"},
        batch_id="TEST_BATCH",
        output_dir=out_dir
    )

    assert "PAYMENT GATEWAY FEE DISPUTE CLAIM NOTICE" in draft_md
    assert "TEST-123" in draft_md
    assert "TXN_L1" in draft_md
    assert "₹5.90" in draft_md
    assert os.path.exists(os.path.join(out_dir, "dispute_draft_TEST_BATCH.md"))

def test_create_run_manifest(tmp_path):
    m_dir = str(tmp_path / "manifests")
    test_file = str(tmp_path / "test.csv")
    with open(test_file, "w") as f:
        f.write("a,b,c\n1,2,3")

    m_path = create_run_manifest(
        settlement_file=test_file,
        rules_version="1.0",
        rules_file=test_file,
        summary_metrics={"total_leakage": 100.0},
        gateway="razorpay",
        manifest_dir=m_dir
    )

    assert os.path.exists(m_path)
    with open(m_path, "r") as f:
        data = json.load(f)
    assert data["gateway"] == "razorpay"
    assert data["inputs"]["rules_version"] == "1.0"
    assert data["metrics"]["total_leakage"] == 100.0
