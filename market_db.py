"""
market_db.py
------------
Persistence layer for the multi-stock platform (SQLite).

Tables
    market_snapshot : latest known state, one row per trading code (upsert)
    price_history   : time series, recorded only for TRACKED stocks
    alert_rules     : user-configured price alerts
    alerts          : log of every alert that fired (sent or failed)
    watchlists      : named groups of trading codes
    app_state       : key/value store (selected stocks, etc.)

All methods are thread-safe: the monitor writes from a background thread
while Streamlit reads from the UI thread. A short-lived connection per
operation keeps SQLite happy across threads.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from config import AppConfig
from market import StockQuote

logger = logging.getLogger(__name__)


class MarketRepository:
    """SQLite store for the whole-market monitoring platform."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.db_path = Path(cfg.market_db_path)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS market_snapshot (
                    code        TEXT PRIMARY KEY,
                    idx         INTEGER,
                    ltp         REAL,
                    high        REAL,
                    low         REAL,
                    close       REAL,
                    ycp         REAL,
                    change      REAL,
                    change_pct  REAL,
                    trades      INTEGER,
                    value_mn    REAL,
                    volume      INTEGER,
                    sector      TEXT,
                    updated_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    code        TEXT NOT NULL,
                    ts          TEXT NOT NULL,
                    ltp         REAL,
                    change      REAL,
                    change_pct  REAL,
                    volume      INTEGER,
                    value_mn    REAL,
                    trades      INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_hist_code_ts
                    ON price_history (code, ts);

                CREATE TABLE IF NOT EXISTS alert_rules (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    code          TEXT NOT NULL,
                    condition     TEXT NOT NULL,   -- above|below|range|outside
                    min_price     REAL,
                    max_price     REAL,
                    enabled       INTEGER NOT NULL DEFAULT 1,
                    cooldown_sec  INTEGER NOT NULL DEFAULT 600,
                    note          TEXT,
                    created_at    TEXT,
                    last_fired_at TEXT
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT NOT NULL,
                    code        TEXT NOT NULL,
                    rule_id     INTEGER,
                    alert_type  TEXT,
                    price       REAL,
                    message     TEXT,
                    sent        INTEGER NOT NULL,
                    error       TEXT
                );

                CREATE TABLE IF NOT EXISTS watchlists (
                    name        TEXT PRIMARY KEY,
                    codes       TEXT NOT NULL,     -- JSON array
                    created_at  TEXT,
                    updated_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            conn.commit()

    # ==================================================================
    # Market snapshot (latest state for every stock)
    # ==================================================================
    def upsert_snapshot(self, quotes: Iterable[StockQuote]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            (q.code, q.index, q.ltp, q.high, q.low, q.close, q.ycp,
             q.change, q.change_pct, q.trades, q.value_mn, q.volume,
             q.sector, ts)
            for q in quotes
        ]
        if not rows:
            return
        try:
            with self._lock, self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO market_snapshot
                        (code, idx, ltp, high, low, close, ycp, change,
                         change_pct, trades, value_mn, volume, sector, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(code) DO UPDATE SET
                        idx=excluded.idx, ltp=excluded.ltp, high=excluded.high,
                        low=excluded.low, close=excluded.close, ycp=excluded.ycp,
                        change=excluded.change, change_pct=excluded.change_pct,
                        trades=excluded.trades, value_mn=excluded.value_mn,
                        volume=excluded.volume, sector=excluded.sector,
                        updated_at=excluded.updated_at
                    """,
                    rows,
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("upsert_snapshot failed: %s", exc)

    def get_snapshot(self) -> pd.DataFrame:
        try:
            with self._lock, self._connect() as conn:
                return pd.read_sql_query(
                    "SELECT * FROM market_snapshot ORDER BY idx ASC", conn
                )
        except Exception as exc:
            logger.error("get_snapshot failed: %s", exc)
            return pd.DataFrame()

    # ==================================================================
    # Price history (tracked stocks only)
    # ==================================================================
    def insert_history(self, quotes: Iterable[StockQuote]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            (q.code, ts, q.ltp, q.change, q.change_pct, q.volume,
             q.value_mn, q.trades)
            for q in quotes
        ]
        if not rows:
            return
        try:
            with self._lock, self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO price_history
                        (code, ts, ltp, change, change_pct, volume, value_mn, trades)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    rows,
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("insert_history failed: %s", exc)

    def get_history(self, code: str, limit: int = 500) -> pd.DataFrame:
        try:
            with self._lock, self._connect() as conn:
                df = pd.read_sql_query(
                    "SELECT ts, ltp, change, change_pct, volume, value_mn, trades "
                    "FROM price_history WHERE code = ? ORDER BY id DESC LIMIT ?",
                    conn, params=(code.upper(), limit),
                )
            return df.iloc[::-1].reset_index(drop=True)  # chronological
        except Exception as exc:
            logger.error("get_history failed: %s", exc)
            return pd.DataFrame()

    def history_points(self, code: str) -> int:
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM price_history WHERE code = ?",
                    (code.upper(),),
                )
                return int(cur.fetchone()[0])
        except sqlite3.Error:
            return 0

    def count_band_hits(self, code: str, low: Optional[float],
                        high: Optional[float],
                        since: Optional[str] = None) -> int:
        """How many times the recorded LTP *entered* the ``[low, high]`` band.

        A "hit" is a transition from outside the band to inside it, so a
        price that lingers inside the band still counts as a single hit.
        This makes the number meaningful regardless of how often the market
        is polled. Counts across the stock's whole recorded price history
        (optionally only rows at/after ``since``).
        """
        if low is None or high is None:
            return 0
        lo, hi = (low, high) if low <= high else (high, low)
        sql = "SELECT ltp FROM price_history WHERE code = ? AND ltp IS NOT NULL"
        params: List[Any] = [code.upper()]
        if since:
            sql += " AND ts >= ?"
            params.append(since)
        sql += " ORDER BY id ASC"
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            logger.error("count_band_hits failed: %s", exc)
            return 0
        hits = 0
        prev_in = False
        for (ltp,) in rows:
            in_band = lo <= ltp <= hi
            if in_band and not prev_in:
                hits += 1
            prev_in = in_band
        return hits

    def count_condition_hits(self, code: str, condition: str,
                             low: Optional[float], high: Optional[float],
                             since: Optional[str] = None) -> int:
        """How many times the recorded LTP *entered* the satisfied state for
        a price condition (``above``/``below``/``range``/``outside``).

        Like :meth:`count_band_hits`, a "hit" is a transition from unsatisfied
        to satisfied, so a price that lingers in the satisfied zone still
        counts once. Counts across the stock's whole recorded history
        (optionally only rows at/after ``since``).
        """
        def satisfied(ltp: float) -> bool:
            if condition == "above":
                return low is not None and ltp >= low
            if condition == "below":
                return high is not None and ltp <= high
            if condition == "outside":
                return (low is not None and high is not None
                        and (ltp < low or ltp > high))
            # "range" (default): inside the band
            return low is not None and high is not None and low <= ltp <= high

        sql = "SELECT ltp FROM price_history WHERE code = ? AND ltp IS NOT NULL"
        params: List[Any] = [code.upper()]
        if since:
            sql += " AND ts >= ?"
            params.append(since)
        sql += " ORDER BY id ASC"
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            logger.error("count_condition_hits failed: %s", exc)
            return 0
        hits = 0
        prev_in = False
        for (ltp,) in rows:
            now_in = satisfied(ltp)
            if now_in and not prev_in:
                hits += 1
            prev_in = now_in
        return hits

    def prune_history(self, retention_days: int) -> None:
        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        try:
            with self._lock, self._connect() as conn:
                conn.execute("DELETE FROM price_history WHERE ts < ?", (cutoff,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("prune_history failed: %s", exc)

    # ==================================================================
    # Alert rules
    # ==================================================================
    def add_rule(self, code: str, condition: str, min_price: Optional[float],
                 max_price: Optional[float], cooldown_sec: int = 600,
                 note: str = "") -> int:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO alert_rules
                        (code, condition, min_price, max_price, enabled,
                         cooldown_sec, note, created_at)
                    VALUES (?,?,?,?,1,?,?,?)
                    """,
                    (code.upper(), condition, min_price, max_price,
                     cooldown_sec, note, ts),
                )
                conn.commit()
                return int(cur.lastrowid)
        except sqlite3.Error as exc:
            logger.error("add_rule failed: %s", exc)
            return -1

    def get_rules(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        try:
            with self._lock, self._connect() as conn:
                conn.row_factory = sqlite3.Row
                sql = "SELECT * FROM alert_rules"
                if enabled_only:
                    sql += " WHERE enabled = 1"
                sql += " ORDER BY code ASC, id ASC"
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as exc:
            logger.error("get_rules failed: %s", exc)
            return []

    def set_rule_enabled(self, rule_id: int, enabled: bool) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE alert_rules SET enabled = ? WHERE id = ?",
                    (int(enabled), rule_id),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("set_rule_enabled failed: %s", exc)

    def mark_rule_fired(self, rule_id: int, when: datetime) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE alert_rules SET last_fired_at = ? WHERE id = ?",
                    (when.strftime("%Y-%m-%d %H:%M:%S"), rule_id),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("mark_rule_fired failed: %s", exc)

    def delete_rule(self, rule_id: int) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("delete_rule failed: %s", exc)

    # ==================================================================
    # Alert log
    # ==================================================================
    def log_alert(self, code: str, rule_id: Optional[int], alert_type: str,
                  price: Optional[float], message: str, sent: bool,
                  error: str = "") -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO alerts
                        (ts, code, rule_id, alert_type, price, message, sent, error)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (ts, code.upper(), rule_id, alert_type, price, message,
                     int(sent), error),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("log_alert failed: %s", exc)

    def recent_alerts(self, limit: int = 100) -> pd.DataFrame:
        try:
            with self._lock, self._connect() as conn:
                return pd.read_sql_query(
                    "SELECT ts, code, alert_type, price, message, sent, error "
                    "FROM alerts ORDER BY id DESC LIMIT ?",
                    conn, params=(limit,),
                )
        except Exception as exc:
            logger.error("recent_alerts failed: %s", exc)
            return pd.DataFrame(
                columns=["ts", "code", "alert_type", "price", "message", "sent", "error"]
            )

    def alerts_sent_count(self) -> int:
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute("SELECT COUNT(*) FROM alerts WHERE sent = 1")
                return int(cur.fetchone()[0])
        except sqlite3.Error:
            return 0

    # ==================================================================
    # Watchlists
    # ==================================================================
    def save_watchlist(self, name: str, codes: List[str]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = json.dumps([c.upper() for c in codes])
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO watchlists (name, codes, created_at, updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        codes=excluded.codes, updated_at=excluded.updated_at
                    """,
                    (name.strip(), payload, ts, ts),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("save_watchlist failed: %s", exc)

    def get_watchlists(self) -> Dict[str, List[str]]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT name, codes FROM watchlists ORDER BY name ASC"
                ).fetchall()
            out: Dict[str, List[str]] = {}
            for name, codes in rows:
                try:
                    out[name] = list(json.loads(codes))
                except json.JSONDecodeError:
                    out[name] = []
            return out
        except sqlite3.Error as exc:
            logger.error("get_watchlists failed: %s", exc)
            return {}

    def delete_watchlist(self, name: str) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute("DELETE FROM watchlists WHERE name = ?", (name,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("delete_watchlist failed: %s", exc)

    # ==================================================================
    # Key/value app state (selected stocks, etc.)
    # ==================================================================
    def set_state(self, key: str, value: Any) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO app_state (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("set_state failed: %s", exc)

    def get_state(self, key: str, default: Any = None) -> Any:
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (key,)
                ).fetchone()
            if row is None:
                return default
            return json.loads(row[0])
        except (sqlite3.Error, json.JSONDecodeError):
            return default

    # ==================================================================
    def stats(self) -> Dict[str, int]:
        try:
            with self._lock, self._connect() as conn:
                snap = conn.execute("SELECT COUNT(*) FROM market_snapshot").fetchone()[0]
                hist = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
                rules = conn.execute("SELECT COUNT(*) FROM alert_rules").fetchone()[0]
                alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE sent=1").fetchone()[0]
            return {"stocks": snap, "history_rows": hist,
                    "rules": rules, "alerts_sent": alerts}
        except sqlite3.Error:
            return {"stocks": 0, "history_rows": 0, "rules": 0, "alerts_sent": 0}
