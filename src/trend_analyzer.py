"""Trend detection and pattern analysis across audit batches."""

from typing import List, Dict, Any, Optional
import sqlite3
from src.audit_store import AuditStore, DEFAULT_DB_PATH

class TrendAnalyzer:
    def __init__(self, audit_store: Optional[AuditStore] = None):
        self.store = audit_store or AuditStore()

    def analyze_recurring_patterns(self, min_recurring_count: int = 2) -> List[Dict[str, Any]]:
        """
        Analyzes historical batches in SQLite audit store.
        Emits recurring_pattern_alerts when specific leak types persist across multiple batches/months.
        """
        with self.store._get_connection() as conn:
            cursor = conn.cursor()
            # Group by batch_id / month and leak_type
            cursor.execute("""
                SELECT 
                    leak_type,
                    COUNT(DISTINCT batch_id) as batch_count,
                    COUNT(txn_id) as total_occurrences,
                    SUM(leak_amount) as total_leakage
                FROM audit_trail
                WHERE status = 'LEAK'
                GROUP BY leak_type
                HAVING COUNT(DISTINCT batch_id) >= ? OR COUNT(txn_id) >= 3
                ORDER BY total_leakage DESC
            """, (min_recurring_count,))
            
            alerts = []
            for row in cursor.fetchall():
                lt = row["leak_type"]
                b_count = row["batch_count"]
                tot_occ = row["total_occurrences"]
                tot_leak = round(row["total_leakage"], 2)

                recommendation = "Review gateway billing configuration and schedule dispute claim."
                if lt == "WRONG_TIER_APPLIED":
                    recommendation = "Systemic volume bracket mismatch detected - recommend contract renegotiation review with gateway account manager."
                elif lt == "CAP_VIOLATION":
                    recommendation = "Gateway billing engine is ignoring statutory fee cap - automate instant dispute claim generation."
                elif lt == "UPI_NON_ZERO_MDR":
                    recommendation = "Illegal MDR billed on zero-MDR UPI rails - escalate immediately to compliance."

                alerts.append({
                    "leak_type": lt,
                    "batch_occurrences": b_count,
                    "total_leaks": tot_occ,
                    "total_leakage": tot_leak,
                    "alert_level": "HIGH" if tot_leak > 100.0 else "MEDIUM",
                    "message": f"{lt} has recurred across {b_count} batch(es) ({tot_occ} transactions totaling ₹{tot_leak:,.2f}).",
                    "recommendation": recommendation
                })
            return alerts
