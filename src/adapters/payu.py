"""PayU payment gateway adapter."""

from typing import Dict, Any, List
from src.adapters.base import GatewayAdapter
from src.schema import PaymentMethodEnum

class PayUAdapter(GatewayAdapter):
    @property
    def gateway_name(self) -> str:
        return "payu"

    def parse_contract(self, contract_path: str) -> Dict[str, Any]:
        return {
            "gateway": "payu",
            "version": "1.0",
            "rules": {
                "payment_methods": {
                    "UPI": {"type": "flat", "rate_pct": 0.0, "fixed_fee": 0.0},
                    "DOMESTIC_CARD": {"type": "flat", "rate_pct": 2.0, "fixed_fee": 0.0},
                    "NETBANKING": {"type": "flat", "rate_pct": 2.0, "fixed_fee": 0.0}
                }
            }
        }

    def parse_settlement(self, settlement_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
        # Stub for future PayU settlement ingestion
        raise NotImplementedError("PayU settlement ingestion will be available in next release.")

    def normalize_payment_method(self, raw_method: str) -> PaymentMethodEnum:
        return PaymentMethodEnum.normalize(raw_method)
