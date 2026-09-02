import json
import csv
import random

random.seed(42)

def round_curr(val):
    return round(float(val) + 1e-9, 2)

def compute_ground_truth(row):
    """Computes deterministic expected fee, expected GST, and expected total."""
    payment_method = row["payment_method"]
    amount = float(row["amount"])
    volume = float(row["monthly_volume_to_date"])
    is_refund = row["is_refund"] == "True"
    refund_hours = float(row["refund_hours_after_txn"]) if row["refund_hours_after_txn"] != "" else None
    is_instant = row["is_instant_settlement"] == "True"
    risk_rating = row["risk_rating"]

    # Check for contract exceptions
    if payment_method not in ["UPI", "DOMESTIC_CARD", "NETBANKING", "INTERNATIONAL_CARD", "WALLET"]:
        return None, None, None, True, f"Unrecognized payment instrument '{payment_method}'"

    if is_instant and (risk_rating == "SPECIAL_REVIEW" or risk_rating == "" or risk_rating is None):
        return None, None, None, True, "Clause 3.1.b Exception: Instant settlement with unverified risk rating requires manual offline review"

    base_fee = 0.0

    # 1. Base MDR / Processing fee
    if payment_method == "UPI":
        base_fee = 0.0
    elif payment_method == "DOMESTIC_CARD":
        if volume <= 500000.00:
            base_fee = amount * 0.0200
        elif volume <= 2000000.00:
            base_fee = amount * 0.0175
        else:
            base_fee = amount * 0.0150
    elif payment_method == "NETBANKING":
        calc = amount * 0.0180
        base_fee = min(calc, 20.00)
    elif payment_method == "INTERNATIONAL_CARD":
        base_fee = (amount * 0.0300) + 7.00
    elif payment_method == "WALLET":
        base_fee = amount * 0.0210

    # 2. Refund fee
    refund_fee = 0.0
    if is_refund:
        if refund_hours is not None and refund_hours <= 24.0:
            refund_fee = 0.0  # Waived
        else:
            refund_fee = 5.00

    # 3. Instant settlement surcharge
    instant_fee = 0.0
    if is_instant:
        instant_fee = amount * 0.0015

    total_expected_fee = round_curr(base_fee + refund_fee + instant_fee)
    expected_gst = round_curr(total_expected_fee * 0.18)
    expected_total = round_curr(total_expected_fee + expected_gst)

    return total_expected_fee, expected_gst, expected_total, False, None

def generate_dataset():
    records = []
    
    # 1. UPI transactions (20 rows: 18 match, 2 leak)
    for i in range(1, 21):
        txn_id = f"TXN_UPI_{i:04d}"
        amt = random.choice([150.0, 499.0, 1200.0, 3500.0, 8500.0, 15000.0])
        vol = round_curr(50000 + i * 25000)
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 10:15:00",
            "payment_method": "UPI",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Seed 2 leaks
        if i in [7, 14]:
            # Leak: charged 0.5% instead of 0%
            billed_fee = round_curr(amt * 0.005)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "UPI_NON_ZERO_MDR",
                "reason": f"UPI transaction billed at 0.50% MDR instead of contractually agreed 0.00% (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed zero fee for UPI as per Clause 1.1",
            }
        
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 2. Domestic Card Tier 1 (<= 5L volume) (10 rows: 9 match, 1 leak)
    for i in range(1, 11):
        txn_id = f"TXN_CARD_T1_{i:04d}"
        amt = random.choice([1200.0, 2400.0, 4500.0, 7800.0, 12000.0])
        vol = round_curr(50000 + i * 40000) # <= 450k
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 11:30:00",
            "payment_method": "DOMESTIC_CARD",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        if i == 5:
            # Leak: charged 2.25% instead of 2.0%
            billed_fee = round_curr(amt * 0.0225)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "CARD_TIER1_OVERCHARGE",
                "reason": f"Card Tier 1 billed at 2.25% MDR instead of contracted 2.00% (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed at Tier 1 rate (2.00%) as per Clause 1.2",
            }
        
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 3. Domestic Card Tier 2 (5L < vol <= 20L) (15 rows: 12 match, 3 leaks)
    for i in range(1, 16):
        txn_id = f"TXN_CARD_T2_{i:04d}"
        amt = random.choice([2500.0, 5000.0, 10000.0, 18000.0, 25000.0])
        vol = round_curr(550000 + i * 85000) # 550k to 1.8M
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 14:00:00",
            "payment_method": "DOMESTIC_CARD",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "MEDIUM",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Leaks on i in [3, 8, 12] - charged Tier 1 rate (2.0%) instead of Tier 2 rate (1.75%)
        if i in [3, 8, 12]:
            billed_fee = round_curr(amt * 0.0200)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "WRONG_TIER_APPLIED",
                "reason": f"Volume at ₹{vol:,.2f} qualifies for Tier 2 (1.75% MDR), but was charged Tier 1 (2.00% MDR) (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed at Tier 2 rate (1.75%) as per Clause 1.2",
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 4. Domestic Card Tier 3 (> 20L volume) (8 rows: 6 match, 2 leaks)
    for i in range(1, 9):
        txn_id = f"TXN_CARD_T3_{i:04d}"
        amt = random.choice([8000.0, 15000.0, 30000.0, 50000.0])
        vol = round_curr(2100000 + i * 120000) # > 2.1M
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 16:20:00",
            "payment_method": "DOMESTIC_CARD",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Leaks on i in [2, 6] - charged Tier 2 rate (1.75%) instead of Tier 3 (1.50%)
        if i in [2, 6]:
            billed_fee = round_curr(amt * 0.0175)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "WRONG_TIER_APPLIED",
                "reason": f"Volume at ₹{vol:,.2f} qualifies for Tier 3 Enterprise (1.50% MDR), but was charged Tier 2 (1.75% MDR) (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed at Tier 3 Enterprise rate (1.50%) as per Clause 1.2",
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 5. Netbanking (8 rows: 6 match, 2 leaks where ₹20 cap was ignored)
    for i in range(1, 9):
        txn_id = f"TXN_NB_{i:04d}"
        # Large amounts to test ₹20 cap
        amt = [800.0, 1000.0, 1500.0, 2500.0, 4000.0, 6000.0, 8000.0, 12000.0][i-1]
        vol = round_curr(300000 + i * 50000)
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 12:45:00",
            "payment_method": "NETBANKING",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Leaks on i in [4, 7]: cap ignored (billed uncapped 1.80%)
        if i in [4, 7]:
            billed_fee = round_curr(amt * 0.0180) # e.g. 2500 * 0.018 = 45 vs 20 cap
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "CAP_VIOLATION",
                "reason": f"Netbanking ₹20.00 fee cap ignored; charged uncapped 1.80% fee ₹{billed_fee:.2f} instead of ₹20.00 (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed Netbanking rate with ₹20.00 cap respected as per Clause 1.3",
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 6. International Cards (5 rows: 3 match, 2 leaks)
    for i in range(1, 6):
        txn_id = f"TXN_INTL_{i:04d}"
        amt = random.choice([4000.0, 8500.0, 15000.0, 22000.0])
        vol = round_curr(400000 + i * 70000)
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 18:10:00",
            "payment_method": "INTERNATIONAL_CARD",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Leaks on i in [2, 4]: billed 3.50% + 10.0 fixed fee
        if i in [2, 4]:
            billed_fee = round_curr((amt * 0.0350) + 10.00)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "INTL_RATE_SURCHARGE_OVERCHARGE",
                "reason": f"International Card billed at 3.50% + ₹10.00 instead of contracted 3.00% + ₹7.00 (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed International Card rate (3.00% + ₹7.00) as per Clause 1.4",
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 7. Wallets & BNPL (4 rows: 3 match, 1 leak)
    for i in range(1, 5):
        txn_id = f"TXN_WALLET_{i:04d}"
        amt = random.choice([600.0, 1500.0, 3200.0, 5000.0])
        vol = round_curr(200000 + i * 40000)
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 19:30:00",
            "payment_method": "WALLET",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "False",
            "refund_hours_after_txn": "",
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        if i == 2:
            # Leak: billed 2.50% instead of 2.10%
            billed_fee = round_curr(amt * 0.0250)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "WALLET_OVERCHARGE",
                "reason": f"Wallet transaction billed at 2.50% MDR instead of contracted 2.10% (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed Wallet rate (2.10%) as per Clause 1.5",
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 8. Refunds (8 rows: 4 under 24h [2 match, 2 leak], 4 over 24h [4 match])
    for i in range(1, 9):
        txn_id = f"TXN_REFUND_{i:04d}"
        amt = random.choice([500.0, 1200.0, 2500.0, 4000.0])
        vol = round_curr(600000 + i * 50000)
        # i 1..4: hours <= 24 (e.g. 4.5, 12.0, 18.2, 23.5)
        # i 5..8: hours > 24 (e.g. 36.0, 72.5, 120.0, 240.0)
        hours = [4.5, 11.2, 18.0, 22.5, 36.0, 48.5, 96.0, 144.0][i-1]
        
        row = {
            "txn_id": txn_id,
            "created_at": f"2025-01-{i%28+1:02d} 09:00:00",
            "payment_method": "DOMESTIC_CARD",
            "amount": amt,
            "monthly_volume_to_date": vol,
            "is_refund": "True",
            "refund_hours_after_txn": hours,
            "is_instant_settlement": "False",
            "risk_rating": "LOW",
        }
        exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
        
        # Leaks on i in [2, 3]: initiated < 24h, but ₹5.00 refund processing fee was billed
        if i in [2, 3]:
            billed_fee = round_curr(exp_fee + 5.00)
            billed_gst = round_curr(billed_fee * 0.18)
            billed_tot = round_curr(billed_fee + billed_gst)
            leak_info = {
                "is_leak": True,
                "leak_type": "MISSED_REFUND_WAIVER",
                "reason": f"Refund initiated at {hours} hrs (<= 24 hrs) qualified for full fee waiver under Clause 2.2, but was billed ₹5.00 fee + GST (Overcharged ₹{round_curr(billed_tot - exp_tot):.2f})",
            }
        else:
            billed_fee = exp_fee
            billed_gst = exp_gst
            billed_tot = exp_tot
            if hours <= 24.0:
                reason = f"Accurately waived ₹5 refund fee for refund initiated at {hours} hrs (< 24 hrs) as per Clause 2.2"
            else:
                reason = f"Accurately billed standard ₹5 refund fee for refund initiated at {hours} hrs (> 24 hrs) as per Clause 2.1"
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": reason,
            }
            
        row["fee_billed"] = billed_fee
        row["gst_billed"] = billed_gst
        row["total_billed"] = billed_tot
        records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # 9. Instant Settlements & Exception cases (5 rows: 2 valid instant match, 3 exceptions)
    for i in range(1, 6):
        txn_id = f"TXN_INSTANT_{i:04d}"
        amt = random.choice([5000.0, 10000.0, 20000.0])
        vol = round_curr(800000 + i * 60000)
        
        if i == 1:
            # Valid instant settlement (match)
            row = {
                "txn_id": txn_id,
                "created_at": "2025-01-25 01:15:00",
                "payment_method": "DOMESTIC_CARD",
                "amount": amt,
                "monthly_volume_to_date": vol,
                "is_refund": "False",
                "refund_hours_after_txn": "",
                "is_instant_settlement": "True",
                "risk_rating": "LOW",
            }
            exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
            row["fee_billed"] = exp_fee
            row["gst_billed"] = exp_gst
            row["total_billed"] = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed Tier 2 MDR + 0.15% instant settlement fee as per Clause 3.1",
            }
            records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

        elif i == 2:
            # Valid instant settlement with UPI (match)
            row = {
                "txn_id": txn_id,
                "created_at": "2025-01-25 02:30:00",
                "payment_method": "UPI",
                "amount": amt,
                "monthly_volume_to_date": vol,
                "is_refund": "False",
                "refund_hours_after_txn": "",
                "is_instant_settlement": "True",
                "risk_rating": "LOW",
            }
            exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
            row["fee_billed"] = exp_fee
            row["gst_billed"] = exp_gst
            row["total_billed"] = exp_tot
            leak_info = {
                "is_leak": False,
                "leak_type": "NONE",
                "reason": "Accurately billed 0.00% UPI MDR + 0.15% instant settlement fee as per Clause 3.1",
            }
            records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

        elif i == 3:
            # Exception: SPECIAL_REVIEW risk rating on instant settlement
            row = {
                "txn_id": txn_id,
                "created_at": "2025-01-26 03:00:00",
                "payment_method": "DOMESTIC_CARD",
                "amount": amt,
                "monthly_volume_to_date": vol,
                "is_refund": "False",
                "refund_hours_after_txn": "",
                "is_instant_settlement": "True",
                "risk_rating": "SPECIAL_REVIEW",
                "fee_billed": 150.00,
                "gst_billed": 27.00,
                "total_billed": 177.00
            }
            exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
            leak_info = {
                "is_leak": False,
                "leak_type": "EXCEPTION",
                "reason": exc_reason,
            }
            records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

        elif i == 4:
            # Exception: Missing risk_rating on instant settlement
            row = {
                "txn_id": txn_id,
                "created_at": "2025-01-26 04:10:00",
                "payment_method": "DOMESTIC_CARD",
                "amount": amt,
                "monthly_volume_to_date": vol,
                "is_refund": "False",
                "refund_hours_after_txn": "",
                "is_instant_settlement": "True",
                "risk_rating": "",
                "fee_billed": 120.00,
                "gst_billed": 21.60,
                "total_billed": 141.60
            }
            exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
            leak_info = {
                "is_leak": False,
                "leak_type": "EXCEPTION",
                "reason": exc_reason,
            }
            records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

        elif i == 5:
            # Exception: Unrecognized payment instrument (e.g. CRYPTO_PAY)
            row = {
                "txn_id": txn_id,
                "created_at": "2025-01-27 15:45:00",
                "payment_method": "CRYPTO_PAY",
                "amount": amt,
                "monthly_volume_to_date": vol,
                "is_refund": "False",
                "refund_hours_after_txn": "",
                "is_instant_settlement": "False",
                "risk_rating": "LOW",
                "fee_billed": 250.00,
                "gst_billed": 45.00,
                "total_billed": 295.00
            }
            exp_fee, exp_gst, exp_tot, is_exc, exc_reason = compute_ground_truth(row)
            leak_info = {
                "is_leak": False,
                "leak_type": "EXCEPTION",
                "reason": exc_reason,
            }
            records.append((row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info))

    # Write data/settlement.csv
    csv_path = "data/settlement.csv"
    fieldnames = [
        "txn_id", "created_at", "payment_method", "amount",
        "monthly_volume_to_date", "is_refund", "refund_hours_after_txn",
        "is_instant_settlement", "risk_rating",
        "fee_billed", "gst_billed", "total_billed"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r[0])

    # Write data/ground_truth.json
    gt_path = "data/ground_truth.json"
    gt_data = []
    total_leaks = 0
    total_matches = 0
    total_exceptions = 0
    total_leak_amount = 0.0

    for r in records:
        row, exp_fee, exp_gst, exp_tot, is_exc, exc_reason, leak_info = r
        if is_exc:
            status = "exception"
            total_exceptions += 1
            delta = None
        elif leak_info["is_leak"]:
            status = "leak"
            total_leaks += 1
            delta = round_curr(row["total_billed"] - exp_tot)
            total_leak_amount += delta
        else:
            status = "match"
            total_matches += 1
            delta = 0.0

        gt_item = {
            "txn_id": row["txn_id"],
            "status": status,
            "is_leak": leak_info["is_leak"],
            "is_exception": is_exc,
            "leak_type": leak_info["leak_type"],
            "amount": row["amount"],
            "payment_method": row["payment_method"],
            "expected_fee": exp_fee,
            "expected_gst": exp_gst,
            "expected_total": exp_tot,
            "billed_fee": row["fee_billed"],
            "gst_billed": row["gst_billed"],
            "billed_total": row["total_billed"],
            "delta": delta,
            "reason": leak_info["reason"]
        }
        gt_data.append(gt_item)

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": len(gt_data),
            "total_matches": total_matches,
            "total_leaks": total_leaks,
            "total_exceptions": total_exceptions,
            "total_seeded_leak_amount": round_curr(total_leak_amount),
            "records": gt_data
        }, f, indent=2)

    print(f"Generated {len(records)} records in {csv_path} and {gt_path}")
    print(f"Summary: Matches={total_matches}, Leaks={total_leaks} (Leak Rate: {total_leaks/len(records)*100:.1f}%), Exceptions={total_exceptions}")
    print(f"Total Seeded Leakage: ₹{total_leak_amount:,.2f}")

if __name__ == "__main__":
    generate_dataset()
