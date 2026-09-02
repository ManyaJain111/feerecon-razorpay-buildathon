"""Base class for payment gateway adapters."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from src.schema import PaymentMethodEnum

class GatewayAdapter(ABC):
    """Abstract base adapter for payment gateways."""

    @property
    @abstractmethod
    def gateway_name(self) -> str:
        """Returns the unique gateway identifier (e.g. 'razorpay', 'stripe', 'payu')."""
        pass

    @abstractmethod
    def parse_contract(self, contract_path: str) -> Dict[str, Any]:
        """Extracts and standardizes fee rules from gateway pricing contract."""
        pass

    @abstractmethod
    def parse_settlement(self, settlement_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
        """Ingests and cleans gateway settlement transactions into canonical schema."""
        pass

    @abstractmethod
    def normalize_payment_method(self, raw_method: str) -> PaymentMethodEnum:
        """Maps gateway-specific payment rail string to canonical PaymentMethodEnum."""
        pass
