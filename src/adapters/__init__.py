"""Factory and registry for gateway adapters."""

from typing import Dict, Type
from src.adapters.base import GatewayAdapter
from src.adapters.razorpay import RazorpayAdapter
from src.adapters.stripe import StripeAdapter
from src.adapters.payu import PayUAdapter

ADAPTERS: Dict[str, Type[GatewayAdapter]] = {
    "razorpay": RazorpayAdapter,
    "stripe": StripeAdapter,
    "payu": PayUAdapter,
}

def get_gateway_adapter(gateway_name: str = "razorpay") -> GatewayAdapter:
    """Instantiates and returns the adapter for specified gateway."""
    key = gateway_name.lower().strip()
    if key not in ADAPTERS:
        raise ValueError(f"Unsupported gateway '{gateway_name}'. Supported gateways: {list(ADAPTERS.keys())}")
    return ADAPTERS[key]()
