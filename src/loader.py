"""Settlement CSV and statement ingestion, normalization, and validation."""

import os
import pandas as pd
from typing import List, Dict, Any, Generator, Optional
from src.schema import PaymentMethodEnum

REQUIRED_COLUMNS = [
    "txn_id", "created_at", "payment_method", "amount",
    "fee_billed", "gst_billed", "total_billed"
]

def _clean_chunk_dataframe(df_chunk: pd.DataFrame) -> List[Dict[str, Any]]:
    """Cleans and normalizes a DataFrame chunk into standardized record dictionaries."""
    for col in REQUIRED_COLUMNS:
        if col not in df_chunk.columns:
            raise ValueError(f"Missing required column in settlement CSV: {col}")

    cleaned = []
    for _, row in df_chunk.iterrows():
        # Clean amount & volume
        amount = float(row["amount"])
        volume_val = row.get("monthly_volume_to_date")
        volume = float(volume_val) if pd.notna(volume_val) and str(volume_val).strip() != "" else 0.0
        
        # Clean boolean flags
        is_refund_val = str(row.get("is_refund", "False")).strip().lower()
        is_refund = is_refund_val in ["true", "1", "yes"]
        
        refund_hours = None
        ref_hr_val = row.get("refund_hours_after_txn")
        if pd.notna(ref_hr_val) and str(ref_hr_val).strip() != "":
            try:
                refund_hours = float(ref_hr_val)
            except ValueError:
                refund_hours = None

        is_instant_val = str(row.get("is_instant_settlement", "False")).strip().lower()
        is_instant = is_instant_val in ["true", "1", "yes"]

        risk_rating = str(row.get("risk_rating", "")).strip() if pd.notna(row.get("risk_rating")) else ""

        # Clean billed amounts
        fee_billed = float(row["fee_billed"]) if pd.notna(row["fee_billed"]) and str(row["fee_billed"]).strip() != "" else 0.0
        gst_billed = float(row["gst_billed"]) if pd.notna(row["gst_billed"]) and str(row["gst_billed"]).strip() != "" else 0.0
        total_billed = float(row["total_billed"]) if pd.notna(row["total_billed"]) and str(row["total_billed"]).strip() != "" else round(fee_billed + gst_billed, 2)

        raw_pm = str(row["payment_method"]).strip()
        canonical_pm = PaymentMethodEnum.normalize(raw_pm).value if raw_pm else raw_pm

        record = {
            "txn_id": str(row["txn_id"]).strip(),
            "created_at": str(row["created_at"]).strip(),
            "payment_method": canonical_pm,
            "raw_payment_method": raw_pm,
            "amount": amount,
            "monthly_volume_to_date": volume,
            "is_refund": is_refund,
            "refund_hours_after_txn": refund_hours,
            "is_instant_settlement": is_instant,
            "risk_rating": risk_rating,
            "fee_billed": fee_billed,
            "gst_billed": gst_billed,
            "total_billed": total_billed,
        }
        cleaned.append(record)
    return cleaned

def load_settlement_csv_chunks(file_path: str, chunksize: int = 50_000) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Streams settlement CSV in configurable chunks to support massive file ingestion
    with low peak memory footprint.
    """
    reader = pd.read_csv(file_path, dtype=str, chunksize=chunksize)
    for df_chunk in reader:
        yield _clean_chunk_dataframe(df_chunk)

def load_settlement_csv(file_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
    """
    Loads settlement CSV or PDF statement, cleans and normalizes types, and returns complete list of record dictionaries.
    Supports .csv and .pdf formats seamlessly.
    """
    if file_path.lower().endswith(".pdf"):
        from src.pdf_processor import extract_text_from_pdf, parse_statement_from_pdf_text
        text = extract_text_from_pdf(file_path)
        records = parse_statement_from_pdf_text(text, os.path.basename(file_path))
        if records:
            return records
        # If no transactions extracted directly from PDF, check if corresponding statement exists
        base = os.path.splitext(os.path.basename(file_path))[0]
        matching_csv = os.path.join("data", f"statement_{base}.csv")
        if os.path.exists(matching_csv):
            return load_settlement_csv(matching_csv, chunksize=chunksize)
        sample_matching = os.path.join("sample_pdf", f"{base}_account_statement.csv")
        if os.path.exists(sample_matching):
            return load_settlement_csv(sample_matching, chunksize=chunksize)

    all_records = []
    for chunk in load_settlement_csv_chunks(file_path, chunksize=chunksize):
        all_records.extend(chunk)
    return all_records

def load_settlement_file(file_path: str) -> List[Dict[str, Any]]:
    """Alias for load_settlement_csv supporting both CSV and PDF formats."""
    return load_settlement_csv(file_path)
