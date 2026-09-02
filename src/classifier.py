"""Transaction classifier for fee matching, discrepancy detection, and risk-tiering."""

from typing import Dict, Any, List, Optional
import os
import yaml
from src.engine import FeeCalculationEngine, round_curr
from src.schema import SeverityEnum, ConfidenceLevelEnum, LeakTypeEnum

TOLERANCE = 0.01

DEFAULT_SEVERITY_CONFIG = {
    "severity_thresholds": {
        "critical": {"min_amount": 1000.0, "min_percentage": 5.0},
        "moderate": {"min_amount": 100.0, "min_percentage": 1.0},
        "minor": {"min_amount": 0.0, "min_percentage": 0.0}
    },
    "confidence_thresholds": {
        "high": 0.95,
        "medium": 0.85,
        "low": 0.0
    }
}

def load_severity_config(config_path: str = "config/severity_thresholds.yaml") -> Dict[str, Any]:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or DEFAULT_SEVERITY_CONFIG
        except Exception:
            return DEFAULT_SEVERITY_CONFIG
    return DEFAULT_SEVERITY_CONFIG

class TransactionClassifier:
    def __init__(self, engine: FeeCalculationEngine, config_path: str = "config/severity_thresholds.yaml"):
        self.engine = engine
        self.config = load_severity_config(config_path)

    def _determine_severity(self, delta: float, txn_amount: float) -> str:
        """Determines severity tier based on dollar delta and percentage of transaction amount."""
        pct = (delta / txn_amount * 100.0) if txn_amount > 0 else 0.0
        thresh = self.config.get("severity_thresholds", DEFAULT_SEVERITY_CONFIG["severity_thresholds"])
        
        crit = thresh.get("critical", {"min_amount": 1000.0, "min_percentage": 5.0})
        mod = thresh.get("moderate", {"min_amount": 100.0, "min_percentage": 1.0})

        if delta >= crit.get("min_amount", 1000.0) or pct >= crit.get("min_percentage", 5.0):
            return SeverityEnum.CRITICAL.value
        elif delta >= mod.get("min_amount", 100.0) or pct >= mod.get("min_percentage", 1.0):
            return SeverityEnum.MODERATE.value
        else:
            return SeverityEnum.MINOR.value

    def _determine_confidence(self, rule_conf: float, needs_review: bool) -> str:
        """Derives leak confidence from rule extraction certainty and needs_review flag."""
        if needs_review or rule_conf < 0.85:
            return ConfidenceLevelEnum.LOW.value
        elif rule_conf >= 0.95:
            return ConfidenceLevelEnum.HIGH.value
        else:
            return ConfidenceLevelEnum.MEDIUM.value

    def classify_transaction(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies a single transaction into MATCH, LEAK, or EXCEPTION.
        """
        calc_result = self.engine.compute_expected_fee(txn)
        rule_conf = float(calc_result.get("rule_confidence", 0.95))
        needs_review = bool(calc_result.get("needs_review", False))
        source_span = calc_result.get("source_span", "")

        # 1. Exception case
        if calc_result["status"] == "exception":
            return {
                "txn_id": txn["txn_id"],
                "created_at": txn.get("created_at", ""),
                "status": "EXCEPTION",
                "is_leak": False,
                "is_exception": True,
                "leak_type": LeakTypeEnum.CONTRACT_EXCEPTION.value,
                "payment_method": txn["payment_method"],
                "amount": txn["amount"],
                "expected_fee": None,
                "expected_gst": None,
                "expected_total": None,
                "billed_fee": txn["fee_billed"],
                "billed_gst": txn["gst_billed"],
                "billed_total": txn["total_billed"],
                "delta": None,
                "severity": SeverityEnum.NONE.value,
                "confidence": ConfidenceLevelEnum.LOW.value if needs_review else ConfidenceLevelEnum.HIGH.value,
                "source_span": source_span,
                "needs_review": True,
                "reason": calc_result["exception_reason"],
                "formula_audit": "N/A (Exception encountered)"
            }

        expected_fee = calc_result["expected_fee"]
        expected_gst = calc_result["expected_gst"]
        expected_total = calc_result["expected_total"]
        billed_total = txn["total_billed"]
        billed_fee = txn["fee_billed"]

        delta = round_curr(billed_total - expected_total)
        confidence_level = self._determine_confidence(rule_conf, needs_review)

        # 2. Match case
        if abs(delta) <= TOLERANCE:
            return {
                "txn_id": txn["txn_id"],
                "created_at": txn.get("created_at", ""),
                "status": "MATCH",
                "is_leak": False,
                "is_exception": False,
                "leak_type": LeakTypeEnum.NONE.value,
                "payment_method": txn["payment_method"],
                "amount": txn["amount"],
                "expected_fee": expected_fee,
                "expected_gst": expected_gst,
                "expected_total": expected_total,
                "billed_fee": billed_fee,
                "billed_gst": txn["gst_billed"],
                "billed_total": billed_total,
                "delta": 0.0,
                "severity": SeverityEnum.NONE.value,
                "confidence": confidence_level,
                "source_span": source_span,
                "needs_review": needs_review,
                "reason": "Billed fee perfectly matches contract rate schedule.",
                "formula_audit": calc_result["formula_audit"]
            }

        # 3. Leak case (Overbilled)
        elif delta > TOLERANCE:
            leak_type = LeakTypeEnum.FEE_OVERCHARGE.value
            pm = txn["payment_method"]
            vol = txn.get("monthly_volume_to_date", 0.0)
            
            if pm == "UPI" and billed_fee > 0.0:
                leak_type = LeakTypeEnum.UPI_NON_ZERO_MDR.value
                diag_reason = f"UPI charged ₹{billed_total:.2f}; contract mandates 0.0% MDR (Leakage: ₹{delta:.2f})."
            elif pm == "DOMESTIC_CARD" and vol > 500000.0:
                leak_type = LeakTypeEnum.WRONG_TIER_APPLIED.value
                diag_reason = f"Card volume ₹{vol:,.2f} entitled to lower tier, but charged higher tier (Leakage: ₹{delta:.2f})."
            elif pm == "NETBANKING" and billed_fee > 20.0:
                leak_type = LeakTypeEnum.CAP_VIOLATION.value
                diag_reason = f"Netbanking ₹20 fee cap ignored (Billed base fee ₹{billed_fee:.2f} > ₹20.00 max cap; Leakage: ₹{delta:.2f})."
            elif txn.get("is_refund") and txn.get("refund_hours_after_txn") is not None and float(txn["refund_hours_after_txn"]) <= 24.0:
                leak_type = LeakTypeEnum.MISSED_REFUND_WAIVER.value
                diag_reason = f"Refund within {txn['refund_hours_after_txn']}h (< 24h) charged refund processing fee instead of waiver (Leakage: ₹{delta:.2f})."
            elif pm == "INTERNATIONAL_CARD":
                leak_type = LeakTypeEnum.INTL_RATE_SURCHARGE_OVERCHARGE.value
                diag_reason = f"International Card billed ₹{billed_total:.2f} vs expected ₹{expected_total:.2f} (Leakage: ₹{delta:.2f})."
            elif pm == "WALLET":
                leak_type = LeakTypeEnum.WALLET_OVERCHARGE.value
                diag_reason = f"Wallet billed ₹{billed_total:.2f} vs expected ₹{expected_total:.2f} (Leakage: ₹{delta:.2f})."
            else:
                diag_reason = f"Billed total ₹{billed_total:.2f} exceeds contract rate ₹{expected_total:.2f} (Leakage: ₹{delta:.2f})."

            severity = self._determine_severity(delta, txn["amount"])

            return {
                "txn_id": txn["txn_id"],
                "created_at": txn.get("created_at", ""),
                "status": "LEAK",
                "is_leak": True,
                "is_exception": False,
                "leak_type": leak_type,
                "payment_method": txn["payment_method"],
                "amount": txn["amount"],
                "expected_fee": expected_fee,
                "expected_gst": expected_gst,
                "expected_total": expected_total,
                "billed_fee": billed_fee,
                "billed_gst": txn["gst_billed"],
                "billed_total": billed_total,
                "delta": delta,
                "severity": severity,
                "confidence": confidence_level,
                "source_span": source_span,
                "needs_review": needs_review,
                "reason": diag_reason,
                "formula_audit": calc_result["formula_audit"]
            }

        # 4. Underbilled
        else:
            return {
                "txn_id": txn["txn_id"],
                "created_at": txn.get("created_at", ""),
                "status": "UNDERCHARGE",
                "is_leak": False,
                "is_exception": False,
                "leak_type": LeakTypeEnum.GATEWAY_UNDERCHARGE.value,
                "payment_method": txn["payment_method"],
                "amount": txn["amount"],
                "expected_fee": expected_fee,
                "expected_gst": expected_gst,
                "expected_total": expected_total,
                "billed_fee": billed_fee,
                "billed_gst": txn["gst_billed"],
                "billed_total": billed_total,
                "delta": delta,
                "severity": SeverityEnum.NONE.value,
                "confidence": confidence_level,
                "source_span": source_span,
                "needs_review": needs_review,
                "reason": f"Merchant undercharged by gateway: Billed ₹{billed_total:.2f} vs Expected ₹{expected_total:.2f}.",
                "formula_audit": calc_result["formula_audit"]
            }

    def classify_all(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classifies a batch of transactions."""
        return [self.classify_transaction(t) for t in transactions]
