"""Razorpay payment gateway adapter."""

from typing import Dict, Any, List
from src.adapters.base import GatewayAdapter
from src.schema import PaymentMethodEnum
from src.rule_extractor import extract_rules
from src.loader import load_settlement_csv

class RazorpayAdapter(GatewayAdapter):
    @property
    def gateway_name(self) -> str:
        return "razorpay"

    def parse_contract(self, contract_path: str) -> Dict[str, Any]:
        return extract_rules(contract_path)

    def parse_settlement(self, settlement_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
        return load_settlement_csv(settlement_path, chunksize=chunksize)

    def normalize_payment_method(self, raw_method: str) -> PaymentMethodEnum:
        return PaymentMethodEnum.normalize(raw_method)
