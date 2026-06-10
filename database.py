"""
database.py
-----------
Persistence layer: every scrape and every alert is written to SQLite
AND appended to a CSV file. All methods are thread-safe (the scheduler
writes from a background thread while Streamlit reads from the UI thread).
"""

from __future__ import annotations

import csv
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from config import AppConfig

logger = logging.getLogger(__name__)

CSV_FIELDS = ["timestamp", "ltp", "success", "alert_sent", "ai_status", "error"]


class Database:
    """SQLite + CSV logging for scrapes and alerts."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.db_path = Path(cfg.db_path)
        self.csv_path = Path(cfg.csv_log_path)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        # New connection per operation -> safe across threads.
        return sqlite3.connect(self.db_path, timeout=10)

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    ltp         REAL,
                    success     INTEGER NOT NULL,
                    alert_sent  INTEGER NOT NULL DEFAULT 0,
                    ai_status   TEXT,
                    error       TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    alert_type  TEXT NOT NULL,      -- target | anomaly | error
                    price       REAL,
                    message     TEXT,
                    sent        INTEGER NOT NULL,
                    error       TEXT
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------
    def log_scrape(self, timestamp: datetime, ltp: Optional[float],
                   success: bool, alert_sent: bool, ai_status: str,
                   error: str = "") -> None:
        """Record one scrape in SQLite and the CSV file."""
        ts = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO scrape_log (timestamp, ltp, success, alert_sent, ai_status, error) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ts, ltp, int(success), int(alert_sent), ai_status, error),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("SQLite log_scrape failed: %s", exc)

        # CSV mirror (best-effort)
        try:
            new_file = not self.csv_path.exists()
            with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
                if new_file:
                    writer.writeheader()
                writer.writerow({
                    "timestamp": ts, "ltp": ltp, "success": success,
                    "alert_sent": alert_sent, "ai_status": ai_status,
                    "error": error,
                })
        except OSError as exc:
            logger.error("CSV log failed: %s", exc)

    def log_alert(self, timestamp: datetime, alert_type: str,
                  price: Optional[float], message: str, sent: bool,
                  error: str = "") -> None:
        """Record an alert attempt (target / anomaly / error)."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO alerts (timestamp, alert_type, price, message, sent, error) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp.strftime("%Y-%m-%d %H:%M:%S"), alert_type,
                     price, message, int(sent), error),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("SQLite log_alert failed: %s", exc)

    # ------------------------------------------------------------------
    # Readers (used by the dashboard)
    # ------------------------------------------------------------------
    def recent_scrapes(self, limit: int = 200) -> pd.DataFrame:
        try:
            with self._lock, self._connect() as conn:
                return pd.read_sql_query(
                    "SELECT timestamp, ltp, success, alert_sent, ai_status, error "
                    "FROM scrape_log ORDER BY id DESC LIMIT ?",
                    conn, params=(limit,),
                )
        except Exception as exc:
            logger.error("recent_scrapes failed: %s", exc)
            return pd.DataFrame(columns=CSV_FIELDS[:-1])

    def recent_alerts(self, limit: int = 50) -> pd.DataFrame:
        try:
            with self._lock, self._connect() as conn:
                return pd.read_sql_query(
                    "SELECT timestamp, alert_type, price, message, sent "
                    "FROM alerts ORDER BY id DESC LIMIT ?",
                    conn, params=(limit,),
                )
        except Exception as exc:
            logger.error("recent_alerts failed: %s", exc)
            return pd.DataFrame(
                columns=["timestamp", "alert_type", "price", "message", "sent"]
            )

    def stats(self) -> Dict[str, Any]:
        """Aggregate counters for KPI cards."""
        try:
            with self._lock, self._connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM scrape_log")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM scrape_log WHERE success=1")
                ok = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM alerts WHERE sent=1")
                alerts = cur.fetchone()[0]
                return {"total_scrapes": total, "successful_scrapes": ok,
                        "alerts_sent": alerts}
        except sqlite3.Error as exc:
            logger.error("stats failed: %s", exc)
            return {"total_scrapes": 0, "successful_scrapes": 0, "alerts_sent": 0}
