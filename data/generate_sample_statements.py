"""Generates account statement CSV datasets and structured rules JSON for sample PDFs."""

import os
import sys
import csv
import json
import random
from typing import List, Dict, Any

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

random.seed(42)

def round_curr(val: float) -> float:
    return round(float(val) + 1e-9, 2)

def generate_sample_1_axos() -> List[Dict[str, Any]]:
    """
    sample_pdf/1.pdf - Axos Advisor Services
    Advisory trading, custody, wire transfers, money movement, and maintenance.
    """
    rows = []
    instruments = [
        ("UPI", "EFT / ACH Auto Transfer", [150.0, 500.0, 1200.0, 5000.0, 15000.0]),
        ("DOMESTIC_CARD", "Equity / ETF Order (Online)", [2500.0, 7500.0, 15000.0, 45000.0]),
        ("NETBANKING", "Domestic Wire Transfer", [1000.0, 5000.0, 12000.0, 25000.0]),
        ("INTERNATIONAL_CARD", "Foreign ADR / Intl Wire", [5000.0, 15000.0, 35000.0, 80000.0]),
        ("WALLET", "Cash Management Sweep", [300.0, 850.0, 2400.0, 6000.0])
    ]
    
    # 60 transactions
    for i in range(1, 61):
        txn_id = f"AXOS_TXN_{i:04d}"
        created_at = f"2025-08-{(i%28)+1:02d} 11:15:00"
        pm_code, desc, amts = instruments[i % len(instruments)]
        amount = random.choice(amts)
        volume = round_curr(50000.0 + (i * 35000.0))
        is_refund = (i % 12 == 0)
        refund_hours = 12.0 if is_refund and (i % 24 == 0) else (36.0 if is_refund else None)
        is_instant = (i % 15 == 0)
        risk_rating = "SPECIAL_REVIEW" if i == 58 else "LOW"
        
        # Calculate expected
        if pm_code == "UPI":
            base = 0.0
        elif pm_code == "DOMESTIC_CARD":
            if volume <= 500000.0:
                base = amount * 0.02
            elif volume <= 2000000.0:
                base = amount * 0.0175
            else:
                base = amount * 0.0150
        elif pm_code == "NETBANKING":
            base = min(amount * 0.018, 25.00)
        elif pm_code == "INTERNATIONAL_CARD":
            base = (amount * 0.03) + 50.00
        elif pm_code == "WALLET":
            base = amount * 0.021
            
        ref_fee = 0.0
        if is_refund:
            ref_fee = 0.0 if (refund_hours is not None and refund_hours <= 24.0) else 5.00
            
        inst_fee = (amount * 0.0015) if is_instant else 0.0
        exp_base = round_curr(base + ref_fee + inst_fee)
        exp_gst = round_curr(exp_base * 0.18)
        exp_tot = round_curr(exp_base + exp_gst)
        
        # Seed realistic leaks
        if i in [7, 19]:
            # UPI charged non-zero fee
            fee_billed = round_curr(amount * 0.005)
        elif i in [14, 38]:
            # Netbanking cap violation ($35 billed instead of $25 cap)
            fee_billed = round_curr(amount * 0.018)
        elif i in [23, 47]:
            # Wrong tier applied (charged Tier 1 rate in Tier 2)
            fee_billed = round_curr(amount * 0.020)
        elif i in [31]:
            # International fixed fee overcharge
            fee_billed = round_curr((amount * 0.03) + 65.00)
        elif i in [58]:
            # Exception: Special review instant settlement
            fee_billed = exp_base
        else:
            fee_billed = exp_base
            
        gst_billed = round_curr(fee_billed * 0.18)
        tot_billed = round_curr(fee_billed + gst_billed)
        
        rows.append({
            "txn_id": txn_id,
            "created_at": created_at,
            "payment_method": pm_code,
            "amount": amount,
            "monthly_volume_to_date": volume,
            "is_refund": str(is_refund),
            "refund_hours_after_txn": str(refund_hours) if refund_hours is not None else "",
            "is_instant_settlement": str(is_instant),
            "risk_rating": risk_rating,
            "fee_billed": fee_billed,
            "gst_billed": gst_billed,
            "total_billed": tot_billed
        })
    return rows

def generate_sample_2_sfusd() -> List[Dict[str, Any]]:
    """
    sample_pdf/2.pdf - SFUSD & DreamBox Learning
    School district site licenses, PD webinars, student seats, and support add-ons.
    """
    rows = []
    services = [
        ("UPI", "ACH Direct District Transfer", [1500.0, 3000.0, 6500.0]),
        ("DOMESTIC_CARD", "School Site License (Tier 1/2)", [6500.0, 8000.0, 14500.0]),
        ("NETBANKING", "District Portal EFT", [1200.0, 2500.0, 5000.0]),
        ("INTERNATIONAL_CARD", "Specialized Curriculum Module", [2500.0, 4500.0, 7500.0]),
        ("WALLET", "School Site Credit Card / P-Card", [450.0, 950.0, 1800.0])
    ]
    
    # 50 transactions
    for i in range(1, 51):
        txn_id = f"SFUSD_TXN_{i:04d}"
        created_at = f"2018-09-{(i%28)+1:02d} 09:30:00"
        pm_code, desc, amts = services[i % len(services)]
        amount = random.choice(amts)
        volume = round_curr(100000.0 + (i * 40000.0))
        is_refund = (i % 10 == 0)
        refund_hours = 8.0 if is_refund and (i % 20 == 0) else (48.0 if is_refund else None)
        is_instant = (i % 12 == 0)
        risk_rating = "SPECIAL_REVIEW" if i == 48 else "LOW"
        
        # Expected
        if pm_code == "UPI":
            base = 0.0
        elif pm_code == "DOMESTIC_CARD":
            if volume <= 500000.0:
                base = amount * 0.020
            elif volume <= 2000000.0:
                base = amount * 0.0175
            else:
                base = amount * 0.0150
        elif pm_code == "NETBANKING":
            base = min(amount * 0.018, 20.00)
        elif pm_code == "INTERNATIONAL_CARD":
            base = (amount * 0.030) + 7.00
        elif pm_code == "WALLET":
            base = amount * 0.021
            
        ref_fee = 0.0 if not is_refund else (0.0 if refund_hours and refund_hours <= 24.0 else 5.0)
        inst_fee = (amount * 0.0015) if is_instant else 0.0
        exp_base = round_curr(base + ref_fee + inst_fee)
        
        # Seed leaks
        if i in [5, 25]:
            fee_billed = round_curr(amount * 0.004) # Non-zero UPI
        elif i in [15, 35]:
            fee_billed = round_curr(amount * 0.020) # Wrong tier applied
        elif i in [18, 42]:
            fee_billed = round_curr(amount * 0.018) # Netbanking cap missed
        else:
            fee_billed = exp_base
            
        gst_billed = round_curr(fee_billed * 0.18)
        tot_billed = round_curr(fee_billed + gst_billed)
        
        rows.append({
            "txn_id": txn_id,
            "created_at": created_at,
            "payment_method": pm_code,
            "amount": amount,
            "monthly_volume_to_date": volume,
            "is_refund": str(is_refund),
            "refund_hours_after_txn": str(refund_hours) if refund_hours is not None else "",
            "is_instant_settlement": str(is_instant),
            "risk_rating": risk_rating,
            "fee_billed": fee_billed,
            "gst_billed": gst_billed,
            "total_billed": tot_billed
        })
    return rows

def generate_sample_3_huntington() -> List[Dict[str, Any]]:
    """
    sample_pdf/3.pdf - Huntington Strategy Shares & Citibank
    Fund administration, ETF creation/redemption, global custody trades, and ADR safekeeping.
    """
    rows = []
    categories = [
        ("UPI", "AP Creation/Redemption Direct Clear", [50000.0, 150000.0, 500000.0]),
        ("DOMESTIC_CARD", "Fund Admin Asset-Based Fee", [10000.0, 25000.0, 80000.0]),
        ("NETBANKING", "Index Receipt Agency Transfer", [2000.0, 8000.0, 15000.0]),
        ("INTERNATIONAL_CARD", "Global Custody Trade (UK/Japan/Spain)", [12000.0, 45000.0, 120000.0]),
        ("WALLET", "Out-of-Pocket Miscellaneous Expense", [250.0, 600.0, 1500.0])
    ]
    
    # 65 transactions
    for i in range(1, 66):
        txn_id = f"HUNT_TXN_{i:04d}"
        created_at = f"2012-05-{(i%28)+1:02d} 14:20:00"
        pm_code, desc, amts = categories[i % len(categories)]
        amount = random.choice(amts)
        volume = round_curr(200000.0 + (i * 45000.0))
        is_refund = (i % 11 == 0)
        refund_hours = 10.0 if is_refund and (i % 22 == 0) else (40.0 if is_refund else None)
        is_instant = (i % 14 == 0)
        risk_rating = "SPECIAL_REVIEW" if i == 62 else "LOW"
        
        if pm_code == "UPI":
            base = 0.0
        elif pm_code == "DOMESTIC_CARD":
            if volume <= 500000.0:
                base = amount * 0.020
            elif volume <= 2000000.0:
                base = amount * 0.0175
            else:
                base = amount * 0.0150
        elif pm_code == "NETBANKING":
            base = min(amount * 0.018, 20.00)
        elif pm_code == "INTERNATIONAL_CARD":
            base = (amount * 0.030) + 7.00
        elif pm_code == "WALLET":
            base = amount * 0.021
            
        ref_fee = 0.0 if not is_refund else (0.0 if refund_hours and refund_hours <= 24.0 else 5.0)
        inst_fee = (amount * 0.0015) if is_instant else 0.0
        exp_base = round_curr(base + ref_fee + inst_fee)
        
        # Leaks
        if i in [8, 28]:
            fee_billed = round_curr(amount * 0.003) # Non-zero UPI
        elif i in [19, 44]:
            fee_billed = round_curr(amount * 0.020) # Wrong tier applied
        elif i in [22, 53]:
            fee_billed = round_curr(amount * 0.018) # Cap violation
        elif i in [36]:
            fee_billed = round_curr((amount * 0.030) + 25.00) # Global custody surcharge overcharge
        else:
            fee_billed = exp_base
            
        gst_billed = round_curr(fee_billed * 0.18)
        tot_billed = round_curr(fee_billed + gst_billed)
        
        rows.append({
            "txn_id": txn_id,
            "created_at": created_at,
            "payment_method": pm_code,
            "amount": amount,
            "monthly_volume_to_date": volume,
            "is_refund": str(is_refund),
            "refund_hours_after_txn": str(refund_hours) if refund_hours is not None else "",
            "is_instant_settlement": str(is_instant),
            "risk_rating": risk_rating,
            "fee_billed": fee_billed,
            "gst_billed": gst_billed,
            "total_billed": tot_billed
        })
    return rows

def generate_sample_4_btpanorama() -> List[Dict[str, Any]]:
    """
    sample_pdf/4.pdf - eWRAP & BT Panorama Investments
    Wealth platform administration, tiered asset fees, listed brokerage, and GST/RITC.
    """
    rows = []
    types = [
        ("UPI", "Cash Account Direct Credit", [500.0, 1500.0, 4500.0, 12000.0]),
        ("DOMESTIC_CARD", "Asset Administration Fee", [3500.0, 8500.0, 22000.0, 65000.0]),
        ("NETBANKING", "Account-Based Admin Transfer", [1500.0, 3500.0, 9000.0]),
        ("INTERNATIONAL_CARD", "Listed Securities Brokerage Order", [5000.0, 18000.0, 45000.0]),
        ("WALLET", "Cash Management Margin Fee", [250.0, 750.0, 1800.0])
    ]
    
    # 55 transactions
    for i in range(1, 56):
        txn_id = f"BTP_TXN_{i:04d}"
        created_at = f"2026-01-{(i%28)+1:02d} 15:45:00"
        pm_code, desc, amts = types[i % len(types)]
        amount = random.choice(amts)
        volume = round_curr(150000.0 + (i * 38000.0))
        is_refund = (i % 9 == 0)
        refund_hours = 6.0 if is_refund and (i % 18 == 0) else (32.0 if is_refund else None)
        is_instant = (i % 13 == 0)
        risk_rating = "SPECIAL_REVIEW" if i == 52 else "LOW"
        
        if pm_code == "UPI":
            base = 0.0
        elif pm_code == "DOMESTIC_CARD":
            if volume <= 500000.0:
                base = amount * 0.020
            elif volume <= 2000000.0:
                base = amount * 0.0175
            else:
                base = amount * 0.0150
        elif pm_code == "NETBANKING":
            base = min(amount * 0.018, 20.00)
        elif pm_code == "INTERNATIONAL_CARD":
            base = (amount * 0.030) + 7.00
        elif pm_code == "WALLET":
            base = amount * 0.021
            
        ref_fee = 0.0 if not is_refund else (0.0 if refund_hours and refund_hours <= 24.0 else 5.0)
        inst_fee = (amount * 0.0015) if is_instant else 0.0
        exp_base = round_curr(base + ref_fee + inst_fee)
        
        # Leaks
        if i in [6, 24]:
            fee_billed = round_curr(amount * 0.005) # UPI overcharge
        elif i in [16, 40]:
            fee_billed = round_curr(amount * 0.020) # Wrong tier
        elif i in [21, 48]:
            fee_billed = round_curr(amount * 0.018) # Cap breach
        elif i in [33]:
            fee_billed = round_curr((amount * 0.030) + 18.00) # Brokerage surcharge leak
        else:
            fee_billed = exp_base
            
        gst_billed = round_curr(fee_billed * 0.18)
        tot_billed = round_curr(fee_billed + gst_billed)
        
        rows.append({
            "txn_id": txn_id,
            "created_at": created_at,
            "payment_method": pm_code,
            "amount": amount,
            "monthly_volume_to_date": volume,
            "is_refund": str(is_refund),
            "refund_hours_after_txn": str(refund_hours) if refund_hours is not None else "",
            "is_instant_settlement": str(is_instant),
            "risk_rating": risk_rating,
            "fee_billed": fee_billed,
            "gst_billed": gst_billed,
            "total_billed": tot_billed
        })
    return rows

def write_csv(filepath: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fieldnames = [
        "txn_id", "created_at", "payment_method", "amount",
        "monthly_volume_to_date", "is_refund", "refund_hours_after_txn",
        "is_instant_settlement", "risk_rating", "fee_billed", "gst_billed", "total_billed"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] Generated statement CSV: {filepath} ({len(rows)} records)")

def generate_all():
    from src.pdf_processor import extract_rules_from_pdf_text
    
    samples = [
        ("1.pdf", generate_sample_1_axos(), "data/statement_1_axos.csv", "sample_pdf/1_account_statement.csv", "data/rules_1_axos.json"),
        ("2.pdf", generate_sample_2_sfusd(), "data/statement_2_sfusd.csv", "sample_pdf/2_account_statement.csv", "data/rules_2_sfusd.json"),
        ("3.pdf", generate_sample_3_huntington(), "data/statement_3_huntington.csv", "sample_pdf/3_account_statement.csv", "data/rules_3_huntington.json"),
        ("4.pdf", generate_sample_4_btpanorama(), "data/statement_4_btpanorama.csv", "sample_pdf/4_account_statement.csv", "data/rules_4_btpanorama.json")
    ]
    
    for pdf_name, rows, data_csv, sample_csv, rules_json in samples:
        # Write statement CSVs
        write_csv(data_csv, rows)
        write_csv(sample_csv, rows)
        
        # Extract and save matching rules JSON
        rules = extract_rules_from_pdf_text("", pdf_name)
        with open(rules_json, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2)
        print(f"[OK] Generated rules JSON: {rules_json}")

if __name__ == "__main__":
    generate_all()
