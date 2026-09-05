"""Fee-rule schemas, payment method enums, severity tiers, and audit models."""

from enum import Enum
from typing import Dict, Any, List, Optional

class PaymentMethodEnum(str, Enum):
    UPI = "UPI"
    DOMESTIC_CARD = "DOMESTIC_CARD"
    INTERNATIONAL_CARD = "INTERNATIONAL_CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"
    BNPL = "BNPL"
    ACH = "ACH"
    INSTANT_PAYOUT = "INSTANT_PAYOUT"
    LOCAL_METHOD = "LOCAL_METHOD"
    BANK_TRANSFER = "BANK_TRANSFER"
    MULTI_CURRENCY = "MULTI_CURRENCY"
    OTHER = "OTHER"

    @classmethod
    def normalize(cls, method_name: str) -> "PaymentMethodEnum":
        """Normalizes various gateway-specific payment method strings to canonical enum."""
        cleaned = str(method_name).strip().upper().replace(" ", "_").replace("-", "_")
        aliases = {
            "UPI": cls.UPI,
            "UPI_INTENT": cls.UPI,
            "UPI_AUTOPAY": cls.UPI,
            "UPI_COLLECT": cls.UPI,
            "DYNAMIC_QR": cls.UPI,
            "CARD": cls.DOMESTIC_CARD,
            "DOMESTIC_CARD": cls.DOMESTIC_CARD,
            "CARD_DOMESTIC": cls.DOMESTIC_CARD,
            "CREDIT_CARD": cls.DOMESTIC_CARD,
            "DEBIT_CARD": cls.DOMESTIC_CARD,
            "INTERNATIONAL_CARD": cls.INTERNATIONAL_CARD,
            "CARD_INTL": cls.INTERNATIONAL_CARD,
            "INTL_CARD": cls.INTERNATIONAL_CARD,
            "NETBANKING": cls.NETBANKING,
            "NET_BANKING": cls.NETBANKING,
            "NB": cls.NETBANKING,
            "WALLET": cls.WALLET,
            "PREPAID_WALLET": cls.WALLET,
            "PAYTM": cls.WALLET,
            "MOBIKWIK": cls.WALLET,
            "AMAZON_PAY": cls.WALLET,
            "AMAZONPAY": cls.WALLET,
            "BNPL": cls.WALLET,
            "SIMPL": cls.WALLET,
            "LAZYPAY": cls.WALLET,
            "ACH": cls.ACH,
            "ACH_DEBIT": cls.ACH,
            "ACH_DIRECT_DEBIT": cls.ACH,
            "INSTANT_PAYOUT": cls.INSTANT_PAYOUT,
            "INSTANT_SETTLEMENT": cls.INSTANT_PAYOUT,
            "LOCAL_METHOD": cls.LOCAL_METHOD,
            "BANK_TRANSFER": cls.BANK_TRANSFER,
            "WIRE_TRANSFER": cls.BANK_TRANSFER,
            "MULTI_CURRENCY": cls.MULTI_CURRENCY,
        }
        if cleaned in cls.__members__:
            return cls[cleaned]
        return aliases.get(cleaned, cls.OTHER)

class LeakTypeEnum(str, Enum):
    NONE = "NONE"
    UPI_NON_ZERO_MDR = "UPI_NON_ZERO_MDR"
    WRONG_TIER_APPLIED = "WRONG_TIER_APPLIED"
    CAP_VIOLATION = "CAP_VIOLATION"
    MISSED_REFUND_WAIVER = "MISSED_REFUND_WAIVER"
    INTL_RATE_SURCHARGE_OVERCHARGE = "INTL_RATE_SURCHARGE_OVERCHARGE"
    WALLET_OVERCHARGE = "WALLET_OVERCHARGE"
    FEE_OVERCHARGE = "FEE_OVERCHARGE"
    GATEWAY_UNDERCHARGE = "GATEWAY_UNDERCHARGE"
    CONTRACT_EXCEPTION = "CONTRACT_EXCEPTION"

class SeverityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    MODERATE = "MODERATE"
    MINOR = "MINOR"
    NONE = "NONE"

class ConfidenceLevelEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DisputeStatusEnum(str, Enum):
    NONE = "none"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    REJECTED = "rejected"

class DisputeOutcomeEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
