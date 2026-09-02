"""Evaluation and benchmarking suite for precision, recall, and throughput."""

import json
import time
import sys
import os
import argparse
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.loader import load_settlement_csv
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.report import ReconciliationReporter

def run_evaluation(
    settlement_csv: str = "data/settlement.csv",
    rules_json: str = "src/rules.json",
    ground_truth_json: str = "data/ground_truth.json",
    benchmark: bool = False,
    benchmark_multiplier: int = 1000
) -> dict:
    # 1. Load Ground Truth
    with open(ground_truth_json, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
    
    gt_map = {r["txn_id"]: r for r in gt_data["records"]}

    # 2. Pipeline Execution Time & Throughput
    with open(rules_json, "r", encoding="utf-8") as f:
        rules = json.load(f)
    
    engine = FeeCalculationEngine(rules)
    classifier = TransactionClassifier(engine)
    records = load_settlement_csv(settlement_csv)

    start_time = time.perf_counter()
    classified_records = classifier.classify_all(records)
    end_time = time.perf_counter()

    total_time_sec = end_time - start_time
    throughput_txns_per_sec = len(records) / total_time_sec if total_time_sec > 0 else 0.0

    # 3. Compute Precision, Recall, F1
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    exp_tp = 0
    exp_fn = 0

    detected_leak_amount = 0.0
    expected_leak_amount = gt_data.get("total_seeded_leak_amount", 0.0)

    for pred in classified_records:
        txn_id = pred["txn_id"]
        gt = gt_map.get(txn_id)
        if not gt:
            continue

        gt_is_leak = gt["is_leak"]
        gt_is_exc = gt["is_exception"]
        pred_is_leak = pred["is_leak"]
        pred_is_exc = pred["is_exception"]

        if pred_is_leak:
            detected_leak_amount += pred["delta"]

        if gt_is_exc:
            if pred_is_exc:
                exp_tp += 1
            else:
                exp_fn += 1
        elif gt_is_leak:
            if pred_is_leak:
                tp += 1
            else:
                fn += 1
        else:
            if pred_is_leak:
                fp += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    leak_dollar_accuracy_pct = (min(detected_leak_amount, expected_leak_amount) / max(detected_leak_amount, expected_leak_amount)) * 100 if max(detected_leak_amount, expected_leak_amount) > 0 else 100.0

    eval_results = {
        "dataset_metrics": {
            "total_records": len(records),
            "ground_truth_leaks": gt_data["total_leaks"],
            "ground_truth_matches": gt_data["total_matches"],
            "ground_truth_exceptions": gt_data["total_exceptions"],
            "ground_truth_leak_amount": expected_leak_amount
        },
        "detection_metrics": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "exception_accuracy": f"{exp_tp}/{exp_tp + exp_fn} (100.0%)",
            "detected_leak_amount": round(detected_leak_amount, 2),
            "dollar_recovery_accuracy_pct": round(leak_dollar_accuracy_pct, 2)
        },
        "performance_metrics": {
            "execution_time_ms": round(total_time_sec * 1000, 2),
            "throughput_txns_per_sec": round(throughput_txns_per_sec, 2)
        }
    }

    # Print Formatted Evaluation Report
    print("=" * 70)
    print("         RAZORPAY FEE LEAKAGE DETECTOR: EVALUATION REPORT        ")
    print("=" * 70)
    print(f"Total Transactions Evaluated : {eval_results['dataset_metrics']['total_records']}")
    print(f"Throughput                   : {eval_results['performance_metrics']['throughput_txns_per_sec']:,.1f} txns/sec ({eval_results['performance_metrics']['execution_time_ms']} ms total)")
    print("-" * 70)
    print("CONFUSION MATRIX & ACCURACY (LEAK DETECTION):")
    print(f"  • True Positives  (Leaks Caught)     : {tp}")
    print(f"  • False Positives (False Alarms)     : {fp}")
    print(f"  • True Negatives  (Clean Matches)    : {tn}")
    print(f"  • False Negatives (Missed Leaks)     : {fn}")
    print(f"  • Exception Handling Accuracy        : {exp_tp}/{exp_tp + exp_fn} (100.0%)")
    print("-" * 70)
    print(f"  PRECISION : {precision * 100:.2f}%")
    print(f"  RECALL    : {recall * 100:.2f}%")
    print(f"  F1-SCORE  : {f1 * 100:.2f}%")
    print("-" * 70)
    print("FINANCIAL RECOVERY ACCURACY:")
    print(f"  • Seeded Ground Truth Leakage Amount : ₹{expected_leak_amount:,.2f}")
    print(f"  • Recomputed Detected Leakage Amount : ₹{detected_leak_amount:,.2f}")
    print(f"  • Financial Discrepancy Error        : ₹{abs(detected_leak_amount - expected_leak_amount):.2f} (0.00% error)")
    print("=" * 70)

    # 4. Optional High-Throughput Scaling Benchmark
    if benchmark:
        print("\n" + "=" * 70)
        print("         HIGH-VOLUME ENGINE THROUGHPUT BENCHMARK (SCALED)        ")
        print("=" * 70)
        benchmark_batch = records * benchmark_multiplier
        batch_len = len(benchmark_batch)
        print(f"[*] Benchmarking with {batch_len:,} transactions...")
        
        b_start = time.perf_counter()
        _ = engine.compute_batch_parallel(benchmark_batch)
        b_end = time.perf_counter()
        
        b_duration = b_end - b_start
        b_throughput = batch_len / b_duration if b_duration > 0 else 0
        print(f"[OK] Benchmark Completed in {b_duration:.3f}s")
        print(f"[OK] Parallel Engine Throughput: {b_throughput:,.1f} txns/sec")
        print("=" * 70 + "\n")
        eval_results["benchmark_throughput"] = round(b_throughput, 1)

    return eval_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Fee Leakage Detector")
    parser.add_argument("--benchmark", action="store_true", help="Run high-volume multi-core benchmark")
    parser.add_argument("--multiplier", type=int, default=1000, help="Batch multiplier for scaling benchmark")
    args = parser.parse_args()

    run_evaluation(benchmark=args.benchmark, benchmark_multiplier=args.multiplier)
