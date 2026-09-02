# SCHEDULE B: MERCHANT PRICING ANNEXURE & SERVICE FEE SCHEDULE
**Agreement Reference:** RZP-COMM-2025-88492
**Merchant Name:** Zenith Retail Technologies Private Limited
**Effective Date:** January 1, 2025
**Governing Gateway:** Razorpay Software Private Limited

---

## 1. Merchant Discount Rate (MDR) by Payment Instrument

### 1.1 Unified Payments Interface (UPI)
* All standard UPI transactions (UPI AutoPay, UPI Intent, UPI Collect, and Dynamic QR) shall be charged at **0.00% (Zero MDR)** with **₹0.00 fixed platform fee**.

### 1.2 Domestic Debit and Credit Cards (Visa, Mastercard, RuPay)
Domestic card transactions are billed based on cumulative monthly settlement volume processed to date within the current calendar month:
* **Tier 1 (Base Tier):** Monthly volume up to ₹5,00,000 (inclusive) → **2.00% MDR** per transaction.
* **Tier 2 (Growth Tier):** Monthly volume from ₹5,00,000.01 up to ₹20,00,000.00 (inclusive) → **1.75% MDR** per transaction.
* **Tier 3 (Enterprise Tier):** Monthly volume exceeding ₹20,00,000.00 → **1.50% MDR** per transaction.

*Note: The applicable tier rate applies to transactions occurring while the cumulative monthly volume to date sits within that bracket.*

### 1.3 Netbanking
* Standard Netbanking across all supported banks (SBI, HDFC, ICICI, Axis, and others) is charged at a flat rate of **1.80% MDR** per transaction, subject to a maximum fee cap of **₹20.00** per transaction (excluding GST).

### 1.4 International Cards
* International credit and debit cards issued outside the Republic of India shall be charged at **3.00% MDR** plus a flat fixed surcharge of **₹7.00** per transaction.

### 1.5 Digital Wallets & BNPL (Buy Now Pay Later)
* Prepaid wallets (Paytm, Mobikwik, Amazon Pay) and approved BNPL payment rails (Simpl, LazyPay) shall be charged at **2.10% MDR** per transaction.

---

## 2. Refund Processing and Fee Waivers

### 2.1 Standard Refund Processing Fee
* In the event of a customer refund (full or partial), a standard processing fee of **₹5.00** per refund event applies.

### 2.2 24-Hour Express Refund Fee Waiver
* If a refund is initiated within **24 hours** of the original transaction timestamp (`refund_hours_after_txn <= 24.0`), the ₹5.00 refund processing fee is **100% waived (₹0.00)**. Original transaction MDR remains non-refundable.

---

## 3. Special Settlement Clauses & Exceptions

### 3.1 Instant Payout / Early Settlement Surcharge
* Merchant initiated Instant Settlements during non-banking hours / holidays are subject to an additional **0.15% settlement fee**.
* *Exception Clause 3.1.b:* Instant settlements where merchant `risk_rating` is undefined or flagged as tier "SPECIAL_REVIEW" require manual offline authorization and cannot be deterministically settled under automated rate schedules.

---

## 4. Statutory Taxes

* All fees (MDR, fixed fees, and refund processing fees) are subject to applicable **Goods and Services Tax (GST) at 18.00%**, billed concurrently on the monthly settlement report.

---
