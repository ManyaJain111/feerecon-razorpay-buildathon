"""SQLite audit trail and dispute repository with idempotency tracking."""

import sqlite3
import hashlib
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

DEFAULT_DB_PATH = "reports/audit_store.db"

class AuditStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    txn_id TEXT PRIMARY KEY,
                    batch_id TEXT,
                    rule_version TEXT,
                    status TEXT,
                    payment_method TEXT,
                    amount REAL,
                    expected_fee REAL,
                    billed_fee REAL,
                    expected_total REAL,
                    billed_total REAL,
                    leak_amount REAL,
                    leak_type TEXT,
                    severity TEXT,
                    confidence TEXT,
                    dispute_status TEXT DEFAULT 'none',
                    resolution_amount REAL DEFAULT 0.0,
                    idempotency_key TEXT UNIQUE,
                    reason TEXT,
                    timestamp TEXT,
                    raw_json TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON audit_trail(batch_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leak_type ON audit_trail(leak_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON audit_trail(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dispute_status ON audit_trail(dispute_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_idempotency ON audit_trail(idempotency_key)")
            conn.commit()

    @staticmethod
    def compute_idempotency_key(txn_id: str, rule_version: str) -> str:
        """Generates deterministic idempotency key for deduplication."""
        raw = f"{str(txn_id).strip()}_{str(rule_version).strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def save_records(self, records: List[Dict[str, Any]], batch_id: str, rule_version: str = "1.0") -> int:
        """
        Persists classified records to SQLite.
        Uses INSERT OR REPLACE with idempotency key to prevent double counting.
        Returns the number of rows inserted/updated.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                txn_id = r.get("txn_id")
                idemp_key = self.compute_idempotency_key(txn_id, rule_version)
                status = r.get("status", "MATCH")
                pm = r.get("payment_method", "")
                amount = float(r.get("amount", 0.0))
                exp_fee = r.get("expected_fee")
                bill_fee = r.get("billed_fee")
                exp_tot = r.get("expected_total")
                bill_tot = r.get("billed_total")
                delta = r.get("delta") if r.get("delta") is not None else (bill_tot - exp_tot if bill_tot and exp_tot else 0.0)
                leak_amount = delta if r.get("is_leak", False) else 0.0
                leak_type = r.get("leak_type", "NONE")
                severity = r.get("severity", "NONE")
                confidence = r.get("confidence", "HIGH")
                reason = r.get("reason", "")

                cursor.execute("""
                    INSERT INTO audit_trail (
                        txn_id, batch_id, rule_version, status, payment_method,
                        amount, expected_fee, billed_fee, expected_total, billed_total,
                        leak_amount, leak_type, severity, confidence, dispute_status,
                        resolution_amount, idempotency_key, reason, timestamp, raw_json
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT dispute_status FROM audit_trail WHERE txn_id = ?), 'none'),
                        COALESCE((SELECT resolution_amount FROM audit_trail WHERE txn_id = ?), 0.0), ?, ?, ?, ?
                    )
                    ON CONFLICT(txn_id) DO UPDATE SET
                        batch_id = excluded.batch_id,
                        rule_version = excluded.rule_version,
                        status = excluded.status,
                        payment_method = excluded.payment_method,
                        amount = excluded.amount,
                        expected_fee = excluded.expected_fee,
                        billed_fee = excluded.billed_fee,
                        expected_total = excluded.expected_total,
                        billed_total = excluded.billed_total,
                        leak_amount = excluded.leak_amount,
                        leak_type = excluded.leak_type,
                        severity = excluded.severity,
                        confidence = excluded.confidence,
                        idempotency_key = excluded.idempotency_key,
                        reason = excluded.reason,
                        timestamp = excluded.timestamp,
                        raw_json = excluded.raw_json
                """, (
                    txn_id, batch_id, rule_version, status, pm,
                    amount, exp_fee, bill_fee, exp_tot, bill_tot,
                    leak_amount, leak_type, severity, confidence,
                    txn_id, txn_id, idemp_key, reason, now_ts, json.dumps(r)
                ))
                saved_count += 1
            conn.commit()
        return saved_count

    def update_dispute(self, txn_id: str, status: str, resolution_amount: Optional[float] = 0.0) -> bool:
        """Updates the dispute status and resolution amount for a specific transaction."""
        valid_statuses = ["none", "submitted", "acknowledged", "resolved", "rejected"]
        if status.lower() not in valid_statuses:
            raise ValueError(f"Invalid dispute status '{status}'. Must be one of {valid_statuses}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE audit_trail
                SET dispute_status = ?, resolution_amount = ?
                WHERE txn_id = ?
            """, (status.lower(), float(resolution_amount or 0.0), txn_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_dispute_kpis(self) -> Dict[str, Any]:
        """Calculates recovery KPIs: Total Detected Leakage vs Total Recovered Leakage."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN status = 'LEAK' THEN 1 END) as leak_count,
                    COALESCE(SUM(CASE WHEN status = 'LEAK' THEN leak_amount ELSE 0 END), 0) as total_detected_leakage,
                    COALESCE(SUM(resolution_amount), 0) as total_recovered_leakage,
                    COUNT(CASE WHEN dispute_status = 'resolved' THEN 1 END) as resolved_disputes_count,
                    COUNT(CASE WHEN dispute_status = 'submitted' THEN 1 END) as pending_disputes_count
                FROM audit_trail
            """)
            row = cursor.fetchone()
            detected = float(row["leak_count"] and row["total_detected_leakage"] or 0.0)
            recovered = float(row["total_recovered_leakage"] or 0.0)
            recovery_rate = (recovered / detected * 100.0) if detected > 0 else 0.0

            return {
                "total_leaks": row["leak_count"] or 0,
                "total_detected_leakage": round(detected, 2),
                "total_recovered_leakage": round(recovered, 2),
                "recovery_rate_pct": round(recovery_rate, 2),
                "resolved_disputes": row["resolved_disputes_count"] or 0,
                "pending_disputes": row["pending_disputes_count"] or 0
            }

    def query_leaks(self, batch_id: Optional[str] = None, leak_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries leaks from the audit store."""
        query = "SELECT * FROM audit_trail WHERE status = 'LEAK'"
        params = []
        if batch_id:
            query += " AND batch_id = ?"
            params.append(batch_id)
        if leak_type:
            query += " AND leak_type = ?"
            params.append(leak_type)
        query += " ORDER BY leak_amount DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
