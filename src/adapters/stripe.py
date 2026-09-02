"""Stripe payment gateway adapter."""

from typing import Dict, Any, List
from src.adapters.base import GatewayAdapter
from src.schema import PaymentMethodEnum

class StripeAdapter(GatewayAdapter):
    @property
    def gateway_name(self) -> str:
        return "stripe"

    def parse_contract(self, contract_path: str) -> Dict[str, Any]:
        return {
            "gateway": "stripe",
            "version": "1.0",
            "rules": {
                "payment_methods": {
                    "DOMESTIC_CARD": {"type": "flat_plus_fixed", "rate_pct": 2.9, "fixed_fee": 0.30},
                    "INTERNATIONAL_CARD": {"type": "flat_plus_fixed", "rate_pct": 3.9, "fixed_fee": 0.30},
                }
            }
        }

    def parse_settlement(self, settlement_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
        # Stub for future Stripe balance history CSV ingestion
        raise NotImplementedError("Stripe settlement ingestion will be available in next release.")

    def normalize_payment_method(self, raw_method: str) -> PaymentMethodEnum:
        return PaymentMethodEnum.normalize(raw_method)
