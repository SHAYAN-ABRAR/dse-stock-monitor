"""
market_monitor.py
-----------------
Background monitoring engine for the whole DSE market.

A single daemon thread keeps an in-memory cache of every stock fresh by
scraping the latest-share-price page on a cadence. For the subset of
TRACKED stocks (selected on the dashboard + every watchlist member +
every stock with an enabled alert rule) it additionally:

    * appends a row to ``price_history`` (for charts / trend analysis),
    * runs the lightweight AI anomaly analyzer, and
    * evaluates the user's alert rules and fires WhatsApp notifications.

The engine is created once per Streamlit server process (cached via
``st.cache_resource`` in runtime.py) and survives page reruns. All shared
state is guarded by locks and exposed through ``snapshot()`` for the UI.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ai_analyzer import AnalysisResult, PriceAnalyzer
from config import AppConfig, save_user_setting
from market import MarketScraper, StockQuote
from market_db import MarketRepository
from notifier import WhatsAppNotifier
from utils import DHAKA_FMT, is_trading_hours, now_dhaka

logger = logging.getLogger(__name__)

# Canonical display order for a stock's tracked price conditions.
_COND_ORDER = {"above": 0, "below": 1, "range": 2, "outside": 3}


# ----------------------------------------------------------------------
# Alert-rule helpers
# ----------------------------------------------------------------------
def rule_condition_text(rule: Dict[str, Any]) -> str:
    """Human-readable description of an alert rule."""
    c = rule.get("condition")
    lo, hi = rule.get("min_price"), rule.get("max_price")
    if c == "above":
        return f"LTP ≥ {lo:g}" if lo is not None else "LTP above threshold"
    if c == "below":
        return f"LTP ≤ {hi:g}" if hi is not None else "LTP below threshold"
    if c == "range":
        return f"LTP enters {lo:g}–{hi:g}" if lo is not None and hi is not None else "LTP in range"
    if c == "outside":
        return f"LTP exits {lo:g}–{hi:g}" if lo is not None and hi is not None else "LTP outside range"
    return str(c)


def rule_matches(rule: Dict[str, Any], ltp: Optional[float]) -> bool:
    """True when the current LTP satisfies the rule's condition."""
    if ltp is None:
        return False
    c = rule.get("condition")
    lo, hi = rule.get("min_price"), rule.get("max_price")
    if c == "above":
        return lo is not None and ltp >= lo
    if c == "below":
        return hi is not None and ltp <= hi
    if c == "range":
        return lo is not None and hi is not None and lo <= ltp <= hi
    if c == "outside":
        return lo is not None and hi is not None and (ltp < lo or ltp > hi)
    return False


@dataclass
class MarketState:
    """Mutable shared state between the monitor thread and the UI."""

    running: bool = True
    in_trading_hours: bool = False
    trading_hours_reason: str = ""
    last_refresh_time: Optional[datetime] = None
    last_refresh_success: Optional[bool] = None
    last_error: str = ""
    consecutive_errors: int = 0
    stock_count: int = 0
    next_refresh_at: Optional[datetime] = None


class MarketMonitor:
    """Owns the background thread, scraper, repository, notifier, analyzers."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.scraper = MarketScraper(cfg)
        self.repo = MarketRepository(cfg)
        self.notifier = WhatsAppNotifier(cfg)

        self._market: Dict[str, StockQuote] = {}
        self._market_lock = threading.Lock()
        self._analyzers: Dict[str, PriceAnalyzer] = {}
        self._ai_results: Dict[str, AnalysisResult] = {}

        self._state = MarketState(
            running=bool(self.repo.get_state("running", True))
        )
        self._lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_prune: Optional[datetime] = None

        self._ensure_thread()

    # ==================================================================
    # Market cache access (UI thread)
    # ==================================================================
    def all_quotes(self) -> List[StockQuote]:
        with self._market_lock:
            return sorted(self._market.values(), key=lambda q: q.index)

    def get_quote(self, code: str) -> Optional[StockQuote]:
        with self._market_lock:
            return self._market.get(code.upper())

    def market_ready(self) -> bool:
        with self._market_lock:
            return len(self._market) > 0

    def search(self, query: str, limit: int = 50) -> List[StockQuote]:
        """Filter the market by code / index / (heuristic) sector."""
        q = query.strip().lower()
        quotes = self.all_quotes()
        if not q:
            return quotes[:limit]
        out = [
            s for s in quotes
            if q in s.code.lower()
            or q == str(s.index)
            or q in s.sector.lower()
        ]
        return out[:limit]

    def ai_result(self, code: str) -> Optional[AnalysisResult]:
        with self._market_lock:
            return self._ai_results.get(code.upper())

    def ensure_loaded(self, force: bool = False) -> None:
        """Block until the market cache has data (synchronous first load)."""
        if self.market_ready() and not force:
            return
        self._refresh(record=False)

    # ==================================================================
    # Tracked stocks  =  selected ∪ watchlists ∪ enabled-rule codes
    # ==================================================================
    def get_selected(self) -> List[str]:
        return [c.upper() for c in self.repo.get_state("selected_codes", [])]

    def set_selected(self, codes: List[str]) -> None:
        clean = []
        for c in codes:
            cu = c.upper()
            if cu not in clean:
                clean.append(cu)
        self.repo.set_state("selected_codes", clean)
        self._wake_event.set()

    def add_selected(self, code: str) -> None:
        codes = self.get_selected()
        if code.upper() not in codes:
            codes.append(code.upper())
            self.set_selected(codes)

    def remove_selected(self, code: str) -> None:
        codes = [c for c in self.get_selected() if c != code.upper()]
        self.set_selected(codes)

    def tracked_codes(self) -> List[str]:
        codes: set[str] = set(self.get_selected())
        for members in self.repo.get_watchlists().values():
            codes.update(c.upper() for c in members)
        for rule in self.repo.get_rules(enabled_only=True):
            codes.add(str(rule["code"]).upper())
        return sorted(codes)

    # ==================================================================
    # Per-stock LTP conditions (dashboard card: condition setter + counters)
    # ==================================================================
    def get_all_price_bounds(self) -> Dict[str, Any]:
        raw = self.repo.get_state("price_bounds", {}) or {}
        return raw if isinstance(raw, dict) else {}

    def get_price_conditions(self, code: str) -> List[Dict[str, Any]]:
        """Return every tracked price condition for a stock (possibly none).

        Each entry is ``{"condition", "low", "high", "set_at"}`` with
        ``low``/``high`` possibly None for single-threshold conditions.
        A legacy pre-multi-condition value (a single dict) is served as a
        one-item list. Entries come back in canonical above → below →
        range → outside order for stable display.
        """
        raw = self.get_all_price_bounds().get(code.upper())
        if not raw:
            return []
        entries = raw if isinstance(raw, list) else [raw]
        return sorted(
            (e for e in entries if isinstance(e, dict)),
            key=lambda e: _COND_ORDER.get(e.get("condition", "range"), 9),
        )

    def set_price_conditions(
        self, code: str,
        entries: List[Tuple[str, Optional[float], Optional[float]]],
    ) -> None:
        """Replace a stock's full set of tracked price conditions.

        ``entries`` holds ``(condition, low, high)`` tuples — one per tracked
        condition (``above``/``below``/``range``/``outside``, mirroring the
        alert rules; duplicates of a condition are ignored). Single-threshold
        conditions store only the bound they use (``above`` → ``low``;
        ``below`` → ``high``); band conditions store a normalised
        ``low`` ≤ ``high`` pair. An empty list clears the stock entirely.
        """
        ts = now_dhaka(self.cfg).strftime(DHAKA_FMT)
        saved: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for condition, low, high in entries:
            if condition in seen:
                continue
            seen.add(condition)
            entry: Dict[str, Any] = {"condition": condition, "set_at": ts}
            if condition == "above":
                entry["low"], entry["high"] = round(float(low), 4), None
            elif condition == "below":
                entry["low"], entry["high"] = None, round(float(high), 4)
            else:  # range / outside — keep a normalised band
                lo, hi = (low, high) if low <= high else (high, low)
                entry["low"], entry["high"] = round(float(lo), 4), round(float(hi), 4)
            saved.append(entry)

        bounds = self.get_all_price_bounds()
        if saved:
            bounds[code.upper()] = saved
            self.repo.set_state("price_bounds", bounds)
            # Tracking the stock guarantees its price history keeps
            # accumulating so the hit counters stay accurate going forward.
            # (``code`` may be a duplicate-card slot like "ACFL#2" — the
            # tracked stock is always the base code.)
            self.add_selected(code.split("#", 1)[0])
        elif bounds.pop(code.upper(), None) is not None:
            self.repo.set_state("price_bounds", bounds)

    def clear_price_bounds(self, code: str) -> None:
        bounds = self.get_all_price_bounds()
        if bounds.pop(code.upper(), None) is not None:
            self.repo.set_state("price_bounds", bounds)

    # ==================================================================
    # Duplicate dashboard cards ("card copies"): the same stock shown on
    # several cards, each with its OWN conditions + bell, to observe
    # different parameter sets side by side. The original ("mother") card
    # stores its settings under the plain code; copy n under "CODE#n".
    # ==================================================================
    def get_card_copies(self) -> Dict[str, List[int]]:
        """Map of code -> sorted duplicate ids, e.g. ``{"ACFL": [2, 3]}``."""
        raw = self.repo.get_state("card_copies", {}) or {}
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, List[int]] = {}
        for code, ids in raw.items():
            if not isinstance(ids, list):
                continue
            clean = sorted({int(i) for i in ids
                            if isinstance(i, int) or str(i).isdigit()})
            if clean:
                out[str(code).upper()] = clean
        return out

    def add_card_copy(self, source_slot: str) -> str:
        """Add a duplicate card of ``source_slot``'s stock; return its slot.

        The copy starts with a snapshot of the SOURCE card's conditions —
        edit them freely afterwards, the source card is never affected.
        """
        base = source_slot.split("#", 1)[0].upper()
        copies = self.get_card_copies()
        ids = copies.get(base, [])
        new_id = (max(ids) + 1) if ids else 2
        copies[base] = ids + [new_id]
        self.repo.set_state("card_copies", copies)
        new_slot = f"{base}#{new_id}"
        src = self.get_price_conditions(source_slot)
        if src:
            bounds = self.get_all_price_bounds()
            bounds[new_slot] = [dict(e) for e in src]
            self.repo.set_state("price_bounds", bounds)
        return new_slot

    def remove_card_copy(self, slot: str) -> None:
        """Remove one duplicate card and every setting stored under it."""
        base, _, num = slot.upper().partition("#")
        if not num:
            return          # mother cards go through remove_dashboard_stock
        copies = self.get_card_copies()
        ids = [i for i in copies.get(base, []) if str(i) != num]
        if ids:
            copies[base] = ids
        else:
            copies.pop(base, None)
        self.repo.set_state("card_copies", copies)
        self.clear_price_bounds(slot)
        self.set_bell_muted(slot, False)

    def remove_dashboard_stock(self, code: str) -> None:
        """Remove a stock from the dashboard along with its duplicate cards.

        The mother card's conditions and recorded history are kept (so
        re-adding the stock restores them); duplicates are UI constructs,
        so their settings are deleted with them.
        """
        base = code.upper()
        copies = self.get_card_copies()
        for n in copies.pop(base, []):
            slot = f"{base}#{n}"
            self.clear_price_bounds(slot)
            self.set_bell_muted(slot, False)
        self.repo.set_state("card_copies", copies)
        self.remove_selected(base)

    # ==================================================================
    # Per-stock notification bells (YouTube-style 🔔 on each card).
    # A bell is ON by default; muting a stock silences its chime, toast
    # and tab flash without touching its conditions or hit counters.
    # ==================================================================
    def get_bell_muted_codes(self) -> List[str]:
        raw = self.repo.get_state("bell_muted_codes", []) or []
        return [str(c).upper() for c in raw] if isinstance(raw, list) else []

    def is_bell_muted(self, code: str) -> bool:
        return code.upper() in self.get_bell_muted_codes()

    def set_bell_muted(self, code: str, muted: bool) -> None:
        cur = set(self.get_bell_muted_codes())
        if muted:
            cur.add(code.upper())
        else:
            cur.discard(code.upper())
        self.repo.set_state("bell_muted_codes", sorted(cur))

    def band_hits(self, code: str, low: float, high: float) -> int:
        """How many times the recorded LTP has entered the [low, high] band."""
        return self.repo.count_band_hits(code, low, high)

    def condition_hits(self, code: str, condition: str,
                       low: Optional[float], high: Optional[float]) -> int:
        """How many times the recorded LTP has satisfied a price condition."""
        return self.repo.count_condition_hits(code, condition, low, high)

    # ==================================================================
    # Control API
    # ==================================================================
    def start(self) -> None:
        with self._lock:
            self._state.running = True
            self._state.consecutive_errors = 0
        self.repo.set_state("running", True)
        self._ensure_thread()
        self._wake_event.set()
        logger.info("Market monitoring STARTED")

    def stop(self) -> None:
        with self._lock:
            self._state.running = False
            self._state.next_refresh_at = None
        self.repo.set_state("running", False)
        logger.info("Market monitoring STOPPED")

    def refresh_now(self) -> Dict[str, Any]:
        """Force an immediate full-market refresh (records history/alerts
        if monitoring is active). Returns a fresh snapshot."""
        logger.info("Manual market refresh triggered")
        with self._lock:
            record = self._state.running
        self._refresh(record=record)
        return self.snapshot()

    def update_refresh_interval(self, seconds: int) -> None:
        seconds = max(30, int(seconds))
        self.cfg.refresh_interval_seconds = seconds
        save_user_setting("refresh_interval_seconds", seconds)
        self._wake_event.set()
        logger.info("Refresh interval updated to %ds", seconds)

    def update_recipient_number(self, number: str) -> bool:
        self.cfg.recipient_whatsapp_number = number
        self.notifier = WhatsAppNotifier(self.cfg)
        save_user_setting("recipient_whatsapp_number", number)
        return self.notifier.ready

    def update_twilio_credentials(self, sid: str, token: str, sender: str) -> bool:
        self.cfg.twilio_account_sid = sid
        self.cfg.twilio_auth_token = token
        self.cfg.twilio_whatsapp_number = sender
        self.notifier = WhatsAppNotifier(self.cfg)
        save_user_setting("twilio_account_sid", sid)
        save_user_setting("twilio_auth_token", token)
        save_user_setting("twilio_whatsapp_number", sender)
        return self.notifier.ready

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            s = self._state
            return {
                "running": s.running,
                "in_trading_hours": s.in_trading_hours,
                "trading_hours_reason": s.trading_hours_reason,
                "last_refresh_time": s.last_refresh_time,
                "last_refresh_success": s.last_refresh_success,
                "last_error": s.last_error,
                "consecutive_errors": s.consecutive_errors,
                "stock_count": s.stock_count,
                "next_refresh_at": s.next_refresh_at,
            }

    # ==================================================================
    # Background loop
    # ==================================================================
    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop, name="dse-market-monitor", daemon=True
            )
            self._thread.start()

    def _run_loop(self) -> None:
        logger.info("Market monitor thread started")
        # Immediate first load so the UI has data to show.
        try:
            self._refresh(record=False)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Initial market load failed: %s", exc)

        while not self._stop_event.is_set():
            open_now, reason = is_trading_hours(self.cfg)
            with self._lock:
                self._state.in_trading_hours = open_now
                self._state.trading_hours_reason = reason
                running = self._state.running

            record = running and open_now
            try:
                self._refresh(record=record)
            except Exception as exc:  # absolute safety net
                logger.exception("Refresh cycle error: %s", exc)

            # Gentle cadence: full speed while the market is live, slower
            # when it is closed (prices are static then anyway).
            if open_now:
                sleep_s = self.cfg.refresh_interval_seconds
            else:
                sleep_s = max(self.cfg.refresh_interval_seconds, 300)
            self._sleep_interruptibly(sleep_s)
        logger.info("Market monitor thread exiting")

    def _sleep_interruptibly(self, seconds: float) -> None:
        with self._lock:
            self._state.next_refresh_at = (
                now_dhaka(self.cfg) + timedelta(seconds=seconds)
            )
        self._wake_event.clear()
        self._wake_event.wait(timeout=seconds)

    # ------------------------------------------------------------------
    def _refresh(self, record: bool) -> None:
        """Scrape the whole market, update caches, and (optionally) record
        history + evaluate alerts for tracked stocks."""
        with self._refresh_lock:
            snap = self.scraper.fetch_all()
            ts = now_dhaka(self.cfg)

            if not snap.success or snap.count == 0:
                with self._lock:
                    self._state.last_refresh_time = ts
                    self._state.last_refresh_success = False
                    self._state.last_error = snap.error
                    self._state.consecutive_errors += 1
                logger.warning("Market refresh failed: %s", snap.error)
                return

            with self._market_lock:
                self._market = {q.code: q for q in snap.quotes}
            with self._lock:
                self._state.last_refresh_time = ts
                self._state.last_refresh_success = True
                self._state.last_error = ""
                self._state.consecutive_errors = 0
                self._state.stock_count = snap.count

            # Persist the latest snapshot of the whole market (cheap upsert).
            self.repo.upsert_snapshot(snap.quotes)

            if not record:
                return

            tracked = set(self.tracked_codes())
            if not tracked:
                return
            tracked_quotes = [q for q in snap.quotes if q.code in tracked]

            # 1) History
            self.repo.insert_history(tracked_quotes)

            # 2) AI analysis per tracked stock
            self._run_ai(tracked_quotes)

            # 3) Alert evaluation
            self._evaluate_alerts(tracked_quotes, ts)

            # 4) Occasional housekeeping (once per day)
            if (self._last_prune is None
                    or (ts - self._last_prune).total_seconds() > 86_400):
                self.repo.prune_history(self.cfg.history_retention_days)
                self._last_prune = ts

    # ------------------------------------------------------------------
    def _run_ai(self, quotes: List[StockQuote]) -> None:
        if not self.cfg.ai_enabled:
            return
        for q in quotes:
            if q.ltp is None:
                continue
            analyzer = self._analyzers.get(q.code)
            if analyzer is None:
                analyzer = PriceAnalyzer(self.cfg)
                self._analyzers[q.code] = analyzer
            try:
                result = analyzer.add_and_analyze(q.ltp)
                with self._market_lock:
                    self._ai_results[q.code] = result
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("AI analysis failed for %s: %s", q.code, exc)

    # ------------------------------------------------------------------
    def _evaluate_alerts(self, quotes: List[StockQuote], ts: datetime) -> None:
        rules = self.repo.get_rules(enabled_only=True)
        if not rules:
            return
        quote_by_code = {q.code: q for q in quotes}
        ts_str = ts.strftime(DHAKA_FMT)

        for rule in rules:
            code = str(rule["code"]).upper()
            quote = quote_by_code.get(code)
            if quote is None or quote.ltp is None:
                continue
            if not rule_matches(rule, quote.ltp):
                continue
            if self._in_cooldown(rule, ts):
                continue

            condition = rule_condition_text(rule)
            ai = self.ai_result(code)
            note = ai.note if (ai and ai.is_anomaly) else ""
            result = self.notifier.send_stock_alert(
                code, quote.ltp, condition, ts_str,
                change_pct=quote.change_pct, note=note,
            )
            self.repo.log_alert(
                code, rule["id"], rule["condition"], quote.ltp,
                result.message, result.sent, result.error,
            )
            # Mark fired so the cooldown applies (prevents alert spam even
            # when Twilio is misconfigured and the send fails).
            self.repo.mark_rule_fired(rule["id"], ts)
            if result.sent:
                logger.info("Alert sent for %s (%s)", code, condition)
            else:
                logger.warning("Alert for %s NOT sent: %s", code, result.error)

    @staticmethod
    def _in_cooldown(rule: Dict[str, Any], ts: datetime) -> bool:
        last = rule.get("last_fired_at")
        if not last:
            return False
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return False
        # `ts` is tz-aware; compare on naive wall-clock to match stored format.
        elapsed = (ts.replace(tzinfo=None) - last_dt).total_seconds()
        return elapsed < float(rule.get("cooldown_sec", 600))
