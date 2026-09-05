"""Deterministic fee calculation engine supporting single transactions and batch processing."""

from typing import Dict, Any, Tuple, Optional, List
import concurrent.futures
import os

def round_curr(val: float) -> float:
    return round(float(val) + 1e-9, 2)

def calculate_expected_fee(txn: Dict[str, Any], rules_data: Dict[str, Any]) -> Dict[str, Any]:
    """Computes expected fee, GST, and total for a single transaction."""
    contract_rules = rules_data.get("rules", {})
    payment_methods = contract_rules.get("payment_methods", {})
    refund_policy = contract_rules.get("refund_policy", {})
    instant_settlement = contract_rules.get("instant_settlement", {})
    statutory_tax = contract_rules.get("statutory_tax", {})
    gst_rate_pct = float(statutory_tax.get("gst_rate_pct", 18.0))

    pm = txn.get("payment_method", "")
    amt = float(txn.get("amount", 0.0))
    vol = float(txn.get("monthly_volume_to_date", 0.0))
    is_refund = bool(txn.get("is_refund", False))
    refund_hours = txn.get("refund_hours_after_txn")
    is_instant = bool(txn.get("is_instant_settlement", False))
    risk_rating = txn.get("risk_rating", "")

    # 1. Validate payment instrument
    if pm not in payment_methods:
        return {
            "status": "exception",
            "exception_reason": f"Payment method '{pm}' is not covered under contracted rate schedule.",
            "expected_fee": None,
            "expected_gst": None,
            "expected_total": None,
            "rule_confidence": 0.0,
            "source_span": "",
            "needs_review": True,
            "breakdown": {}
        }

    # 2. Validate Instant Settlement conditions
    if is_instant:
        disallowed = instant_settlement.get("disallowed_risk_ratings", ["SPECIAL_REVIEW", ""])
        if risk_rating in disallowed or not risk_rating:
            return {
                "status": "exception",
                "exception_reason": f"Instant settlement with risk rating '{risk_rating}' requires manual offline authorization (Clause 3.1.b).",
                "expected_fee": None,
                "expected_gst": None,
                "expected_total": None,
                "rule_confidence": instant_settlement.get("confidence", 0.94),
                "source_span": instant_settlement.get("source_span", ""),
                "needs_review": instant_settlement.get("needs_review", False),
                "breakdown": {}
            }

    pm_rule = payment_methods[pm]
    rule_type = pm_rule.get("type", "flat")
    base_fee = 0.0
    formula_parts = []
    applied_confidence = pm_rule.get("confidence", 0.95)
    applied_source_span = pm_rule.get("source_span", "")
    applied_needs_review = pm_rule.get("needs_review", False)

    # 3. Calculate Base Processing / MDR Fee
    if rule_type in ("flat", "interchange_plus", "blended_plus_markup"):
        rate_pct = float(pm_rule.get("rate_pct", 0.0))
        fixed_fee = float(pm_rule.get("fixed_fee", 0.0))
        base_fee = (amt * (rate_pct / 100.0)) + fixed_fee
        label = "interchange+" if rule_type == "interchange_plus" else ("blended" if rule_type == "blended_plus_markup" else "flat")
        formula_parts.append(f"{pm} {label} {rate_pct}% + ₹{fixed_fee:.2f} = ₹{base_fee:.2f}")

    elif rule_type in ("tiered_volume", "blended_tiered"):
        tiers = pm_rule.get("tiers", [])
        applied_rate = None
        applied_tier_name = ""
        for tier in tiers:
            min_v = float(tier.get("min_volume", 0.0))
            max_v = tier.get("max_volume")
            if max_v is not None:
                max_v = float(max_v)
                if min_v <= vol <= max_v:
                    applied_rate = float(tier.get("rate_pct", 0.0))
                    applied_tier_name = tier.get("tier_name", f"{min_v}-{max_v}")
                    if "confidence" in tier:
                        applied_confidence = min(applied_confidence, tier["confidence"])
                    break
            else:
                if vol >= min_v:
                    applied_rate = float(tier.get("rate_pct", 0.0))
                    applied_tier_name = tier.get("tier_name", f">{min_v}")
                    if "confidence" in tier:
                        applied_confidence = min(applied_confidence, tier["confidence"])
                    break
        
        if applied_rate is None:
            applied_rate = float(tiers[0].get("rate_pct", 2.0)) if tiers else 2.0
            applied_tier_name = "Default Tier"

        base_fee = amt * (applied_rate / 100.0)
        formula_parts.append(f"Volume ₹{vol:,.2f} qualifies for {applied_tier_name} ({applied_rate}%) -> ₹{amt:.2f} * {applied_rate}% = ₹{base_fee:.2f}")

    elif rule_type == "flat_with_cap":
        rate_pct = float(pm_rule.get("rate_pct", 0.0))
        fee_cap = pm_rule.get("fee_cap")
        fixed_fee = float(pm_rule.get("fixed_fee", 0.0))
        calc = amt * (rate_pct / 100.0)
        if fee_cap is not None and calc > float(fee_cap):
            base_fee = float(fee_cap) + fixed_fee
            formula_parts.append(f"Calculated ₹{calc:.2f} capped at max fee ₹{float(fee_cap):.2f}")
        else:
            base_fee = calc + fixed_fee
            formula_parts.append(f"{rate_pct}% fee = ₹{base_fee:.2f}")

    elif rule_type == "flat_plus_fixed":
        rate_pct = float(pm_rule.get("rate_pct", 0.0))
        fixed_fee = float(pm_rule.get("fixed_fee", 0.0))
        base_fee = (amt * (rate_pct / 100.0)) + fixed_fee
        formula_parts.append(f"({rate_pct}% * ₹{amt:.2f}) + ₹{fixed_fee:.2f} fixed = ₹{base_fee:.2f}")

    # 4. Calculate Refund Processing Fee & Waivers
    refund_fee = 0.0
    if is_refund:
        waiver_window = float(refund_policy.get("waiver_window_hours", 24.0))
        std_fee = float(refund_policy.get("standard_fee", 5.0))
        waived_fee = float(refund_policy.get("waived_fee", 0.0))

        if refund_hours is not None and float(refund_hours) <= waiver_window:
            refund_fee = waived_fee
            formula_parts.append(f"Refund initiated at {refund_hours}h (<= {waiver_window}h): fee waived to ₹{waived_fee:.2f}")
        else:
            refund_fee = std_fee
            hours_str = f"{refund_hours}h" if refund_hours is not None else "unspecified time"
            formula_parts.append(f"Refund initiated at {hours_str} (> {waiver_window}h): fee ₹{std_fee:.2f}")

    # 5. Calculate Instant Settlement Surcharge
    instant_fee = 0.0
    if is_instant:
        instant_rate = float(instant_settlement.get("rate_pct", 0.15))
        instant_fee = amt * (instant_rate / 100.0)
        formula_parts.append(f"Instant settlement surcharge ({instant_rate}%) = ₹{instant_fee:.2f}")

    # Sum expected fee, GST, and total
    total_expected_fee = round_curr(base_fee + refund_fee + instant_fee)
    expected_gst = round_curr(total_expected_fee * (gst_rate_pct / 100.0))
    expected_total = round_curr(total_expected_fee + expected_gst)

    return {
        "status": "success",
        "expected_fee": total_expected_fee,
        "expected_gst": expected_gst,
        "expected_total": expected_total,
        "rule_confidence": applied_confidence,
        "source_span": applied_source_span,
        "needs_review": applied_needs_review,
        "breakdown": {
            "base_fee": round_curr(base_fee),
            "refund_fee": round_curr(refund_fee),
            "instant_fee": round_curr(instant_fee),
            "gst": expected_gst
        },
        "formula_audit": " | ".join(formula_parts)
    }

class FeeCalculationEngine:
    def __init__(self, rules_data: Dict[str, Any]):
        self.rules_data = rules_data
        self.contract_rules = rules_data.get("rules", {})
        self.payment_methods = self.contract_rules.get("payment_methods", {})
        self.refund_policy = self.contract_rules.get("refund_policy", {})
        self.instant_settlement = self.contract_rules.get("instant_settlement", {})
        self.statutory_tax = self.contract_rules.get("statutory_tax", {})
        self.gst_rate_pct = float(self.statutory_tax.get("gst_rate_pct", 18.0))

    def compute_expected_fee(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        """Computes expected fee, GST, and total for a single transaction."""
        return calculate_expected_fee(txn, self.rules_data)

    def compute_batch_parallel(
        self,
        transactions: List[Dict[str, Any]],
        max_workers: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Computes expected fees for large batches in parallel using ProcessPoolExecutor.
        For small batches (<100 items), executes sequentially to avoid IPC overhead.
        """
        if len(transactions) < 100:
            return [self.compute_expected_fee(t) for t in transactions]

        workers = max_workers or min(os.cpu_count() or 4, 8)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            chunk_size = max(1, len(transactions) // (workers * 4))
            futures = [
                executor.submit(_batch_calc_worker, transactions[i:i + chunk_size], self.rules_data)
                for i in range(0, len(transactions), chunk_size)
            ]
            results = []
            for f in futures:
                results.extend(f.result())
            return results

def _batch_calc_worker(chunk: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Worker function for parallel batch processing."""
    return [calculate_expected_fee(t, rules) for t in chunk]
