"""Run manifest generation for run provenance tracking."""

import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def compute_file_sha256(file_path: str) -> str:
    """Computes SHA256 hash of a file."""
    if not os.path.exists(file_path):
        return "FILE_NOT_FOUND"
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def get_git_commit_hash() -> str:
    """Retrieves current git commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def create_run_manifest(
    settlement_file: str,
    rules_version: str,
    rules_file: str,
    summary_metrics: Dict[str, Any],
    gateway: str = "razorpay",
    manifest_dir: str = "reports",
    contract_file: Optional[str] = None
) -> str:
    """
    Creates and saves a run manifest JSON file.
    Returns the file path of the generated manifest.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    settlement_hash = compute_file_sha256(settlement_file)
    rules_hash = compute_file_sha256(rules_file)
    contract_hash = compute_file_sha256(contract_file) if contract_file else "NOT_PROVIDED"
    git_commit = get_git_commit_hash()

    manifest_data = {
        "run_id": f"RUN_{timestamp}",
        "timestamp_utc": now.isoformat(),
        "gateway": gateway,
        "git_commit": git_commit,
        "inputs": {
            "settlement_file": settlement_file,
            "settlement_file_sha256": settlement_hash,
            "contract_file": contract_file or "NOT_PROVIDED",
            "contract_file_sha256": contract_hash,
            "rules_file": rules_file,
            "rules_version": rules_version,
            "rules_sha256": rules_hash
        },
        "metrics": summary_metrics
    }

    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, f"run_manifest_{timestamp}.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_path
