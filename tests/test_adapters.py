import pytest
from src.adapters import get_gateway_adapter
from src.schema import PaymentMethodEnum

def test_gateway_adapter_dispatch():
    rzp = get_gateway_adapter("razorpay")
    assert rzp.gateway_name == "razorpay"

    stripe = get_gateway_adapter("stripe")
    assert stripe.gateway_name == "stripe"

    payu = get_gateway_adapter("payu")
    assert payu.gateway_name == "payu"

    with pytest.raises(ValueError):
        get_gateway_adapter("unsupported_gateway")

def test_payment_method_normalization():
    assert PaymentMethodEnum.normalize("upi_intent") == PaymentMethodEnum.UPI
    assert PaymentMethodEnum.normalize("credit_card") == PaymentMethodEnum.DOMESTIC_CARD
    assert PaymentMethodEnum.normalize("card_intl") == PaymentMethodEnum.INTERNATIONAL_CARD
    assert PaymentMethodEnum.normalize("net_banking") == PaymentMethodEnum.NETBANKING
    assert PaymentMethodEnum.normalize("simpl") == PaymentMethodEnum.WALLET
