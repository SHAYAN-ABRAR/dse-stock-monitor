"""
scheduler.py
------------
Background monitoring engine.

A single daemon thread runs the poll loop:
    every `polling_interval_seconds` (default 120 s):
        1. Check trading hours (unless override is on)  -> skip if closed
        2. Scrape LTP (with retries/fallbacks inside DSEScraper)
        3. Hand the price to the AI analyzer on a worker thread
           (never blocks the alert path)
        4. Check the target range  -> WhatsApp alert (deduped)
        5. Log everything to SQLite + CSV
        6. After N consecutive failures -> WhatsApp error alert + auto-pause

The thread is created once per Streamlit server process (via
st.cache_resource in app.py) and survives page reruns. All shared state
is guarded by a lock and exposed through `snapshot()` for the UI.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ai_analyzer import AnalysisResult, PriceAnalyzer
from config import AppConfig
from database import Database
from notifier import WhatsAppNotifier
from scraper import DSEScraper
from utils import is_trading_hours, now_dhaka

logger = logging.getLogger(__name__)


@dataclass
class MonitorState:
    """Mutable shared state between the monitor thread and the UI."""

    running: bool = False
    override_trading_hours: bool = False
    in_trading_hours: bool = False
    trading_hours_reason: str = ""
    last_price: Optional[float] = None
    last_scrape_time: Optional[datetime] = None
    last_scrape_success: Optional[bool] = None
    last_error: str = ""
    consecutive_errors: int = 0
    paused_due_to_errors: bool = False
    alert_count: int = 0
    last_alert_time: Optional[datetime] = None
    last_alert_status: str = "No alerts yet"
    last_alerted_price: Optional[float] = None
    ai_status: str = "Waiting for data"
    ai_last_result: Optional[AnalysisResult] = None
    next_poll_at: Optional[datetime] = None


class StockMonitor:
    """Owns the background thread, scraper, notifier, analyzer and DB."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.scraper = DSEScraper(cfg)
        self.notifier = WhatsAppNotifier(cfg)
        self.analyzer = PriceAnalyzer(cfg)
        self.db = Database(cfg)

        self._state = MonitorState()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()       # lets Start fire instantly
        self._thread: Optional[threading.Thread] = None
        self._ai_pool = ThreadPoolExecutor(max_workers=1,
                                           thread_name_prefix="ai-analyzer")

    # ==================================================================
    # Public control API (called from the Streamlit UI thread)
    # ==================================================================
    def start(self) -> None:
        """Start (or resume) monitoring immediately."""
        with self._lock:
            self._state.running = True
            self._state.paused_due_to_errors = False
            self._state.consecutive_errors = 0
            self._state.last_error = ""
        self._ensure_thread()
        self._wake_event.set()  # poll right away instead of waiting
        logger.info("Monitoring STARTED")

    def stop(self) -> None:
        """Pause monitoring immediately (thread stays alive, idle)."""
        with self._lock:
            self._state.running = False
            self._state.next_poll_at = None
        logger.info("Monitoring STOPPED")

    def set_override(self, value: bool) -> None:
        with self._lock:
            self._state.override_trading_hours = value
        if value:
            self._wake_event.set()

    def update_target_range(self, low: float, high: float) -> None:
        """Live-edit the target price range from the UI."""
        if low > high:
            low, high = high, low
        self.cfg.target_min_price = low
        self.cfg.target_max_price = high
        logger.info("Target range updated to %.2f-%.2f", low, high)

    def snapshot(self) -> Dict[str, Any]:
        """Thread-safe copy of the current state for rendering."""
        with self._lock:
            s = self._state
            return {
                "running": s.running,
                "override": s.override_trading_hours,
                "in_trading_hours": s.in_trading_hours,
                "trading_hours_reason": s.trading_hours_reason,
                "last_price": s.last_price,
                "last_scrape_time": s.last_scrape_time,
                "last_scrape_success": s.last_scrape_success,
                "last_error": s.last_error,
                "consecutive_errors": s.consecutive_errors,
                "paused_due_to_errors": s.paused_due_to_errors,
                "alert_count": s.alert_count,
                "last_alert_time": s.last_alert_time,
                "last_alert_status": s.last_alert_status,
                "ai_status": s.ai_status,
                "ai_last_result": s.ai_last_result,
                "next_poll_at": s.next_poll_at,
            }

    # ==================================================================
    # Background loop
    # ==================================================================
    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop, name="dse-monitor", daemon=True
            )
            self._thread.start()

    def _run_loop(self) -> None:
        logger.info("Monitor thread started")
        while not self._stop_event.is_set():
            with self._lock:
                running = self._state.running
                override = self._state.override_trading_hours

            open_now, reason = is_trading_hours(self.cfg)
            with self._lock:
                self._state.in_trading_hours = open_now
                self._state.trading_hours_reason = reason

            if running and (open_now or override):
                try:
                    self._poll_once()
                except Exception as exc:  # absolute safety net
                    logger.exception("Unexpected error in poll cycle: %s", exc)
                self._sleep_interruptibly(self.cfg.polling_interval_seconds)
            else:
                # Idle: re-check every 10 s so Start/override reacts fast.
                with self._lock:
                    self._state.next_poll_at = None
                self._sleep_interruptibly(10)
        logger.info("Monitor thread exiting")

    def _sleep_interruptibly(self, seconds: float) -> None:
        """Sleep that wakes early on Start/override toggles."""
        from datetime import timedelta
        with self._lock:
            if self._state.running:
                self._state.next_poll_at = now_dhaka(self.cfg) + timedelta(seconds=seconds)
        self._wake_event.clear()
        self._wake_event.wait(timeout=seconds)

    # ------------------------------------------------------------------
    def _poll_once(self) -> None:
        """One complete scrape -> analyze -> alert -> log cycle."""
        result = self.scraper.fetch_price()
        ts = now_dhaka(self.cfg)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        if not result.success:
            self._handle_failure(result.error, ts)
            self.db.log_scrape(ts, None, False, False, "skipped", result.error)
            return

        price: float = result.price  # type: ignore[assignment]
        with self._lock:
            self._state.last_price = price
            self._state.last_scrape_time = ts
            self._state.last_scrape_success = True
            self._state.consecutive_errors = 0
            self._state.last_error = ""

        # ---- AI analysis on a worker thread (non-blocking) -------------
        ai_note: Optional[str] = None
        ai_status = "disabled"
        if self.cfg.ai_enabled:
            ai_status = "pending"
            future = self._ai_pool.submit(self.analyzer.add_and_analyze, price)
            # Give the (fast) analyzer a short window; if it's slow we
            # proceed with the target-range alert and let the anomaly
            # alert fire from the callback instead.
            try:
                analysis = future.result(timeout=5)
                ai_status = analysis.note
                with self._lock:
                    self._state.ai_status = analysis.note
                    self._state.ai_last_result = analysis
                if analysis.is_anomaly:
                    ai_note = analysis.note
                    self._send_anomaly_alert(price, ts_str, analysis.note, ts)
            except Exception:
                # Analyzer still running/failed -> fire-and-forget callback.
                def _on_done(fut: Any) -> None:
                    try:
                        late = fut.result()
                        with self._lock:
                            self._state.ai_status = late.note
                            self._state.ai_last_result = late
                        if late.is_anomaly:
                            self._send_anomaly_alert(
                                price, ts_str, late.note, now_dhaka(self.cfg))
                    except Exception as exc:
                        logger.error("Async AI analysis failed: %s", exc)
                future.add_done_callback(_on_done)

        # ---- Target-range condition ------------------------------------
        alert_sent = False
        if self.cfg.target_min_price <= price <= self.cfg.target_max_price:
            alert_sent = self._send_target_alert(price, ts_str, ai_note, ts)
        else:
            with self._lock:
                # Price left the range -> allow re-alert on next entry.
                if self._state.last_alerted_price is not None:
                    self._state.last_alerted_price = None

        self.db.log_scrape(ts, price, True, alert_sent, ai_status)

    # ------------------------------------------------------------------
    # Alert helpers
    # ------------------------------------------------------------------
    def _should_send_target_alert(self, price: float, ts: datetime) -> bool:
        """Dedupe: skip identical price re-alerts and respect cooldown."""
        with self._lock:
            s = self._state
            if (not self.cfg.realert_on_same_price
                    and s.last_alerted_price is not None
                    and abs(s.last_alerted_price - price) < 1e-9):
                return False
            if (s.last_alert_time is not None
                    and (ts - s.last_alert_time).total_seconds()
                    < self.cfg.alert_cooldown_seconds
                    and not self.cfg.realert_on_same_price):
                return False
        return True

    def _send_target_alert(self, price: float, ts_str: str,
                           ai_note: Optional[str], ts: datetime) -> bool:
        if not self._should_send_target_alert(price, ts):
            logger.info("Target alert suppressed (dedupe/cooldown).")
            return False
        result = self.notifier.send_target_alert(price, ts_str, ai_note)
        self.db.log_alert(ts, "target", price, result.message,
                          result.sent, result.error)
        with self._lock:
            if result.sent:
                self._state.alert_count += 1
                self._state.last_alert_time = ts
                self._state.last_alerted_price = price
                self._state.last_alert_status = f"✅ Target alert sent at {ts_str} (LTP {price})"
            else:
                self._state.last_alert_status = f"❌ Alert failed: {result.error}"
        return result.sent

    def _send_anomaly_alert(self, price: float, ts_str: str,
                            note: str, ts: datetime) -> None:
        result = self.notifier.send_anomaly_alert(price, ts_str, note)
        self.db.log_alert(ts, "anomaly", price, result.message,
                          result.sent, result.error)
        with self._lock:
            if result.sent:
                self._state.alert_count += 1
                self._state.last_alert_time = ts
                self._state.last_alert_status = f"⚠️ Anomaly alert sent at {ts_str}"

    def _handle_failure(self, error: str, ts: datetime) -> None:
        """Track consecutive failures; alert + auto-pause at the limit."""
        with self._lock:
            self._state.last_scrape_time = ts
            self._state.last_scrape_success = False
            self._state.last_error = error
            self._state.consecutive_errors += 1
            failures = self._state.consecutive_errors
        logger.error("Scrape failure #%d: %s", failures, error)

        if failures >= self.cfg.max_consecutive_failures:
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            result = self.notifier.send_error_alert(error, ts_str)
            self.db.log_alert(ts, "error", None, result.message,
                              result.sent, result.error)
            with self._lock:
                self._state.running = False
                self._state.paused_due_to_errors = True
                self._state.last_alert_status = (
                    f"🚨 Error alert sent; monitoring auto-paused at {ts_str}"
                    if result.sent else
                    f"🚨 Monitoring auto-paused at {ts_str} (error alert failed: {result.error})"
                )
            logger.error("Auto-paused after %d consecutive failures.", failures)
