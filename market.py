"""
market.py
---------
Whole-market scraper for the DSE "Latest Share Price" page.

A single HTTP request to

    https://www.dsebd.org/latest_share_price_scroll_l.php

returns the entire market (~396 instruments) in one HTML table. This
module parses every row into a structured ``StockQuote`` and returns a
``MarketSnapshot``. It never raises to the caller — failures are encoded
in the snapshot so the monitor loop can retry / count errors gracefully.

Table layout (confirmed against the live page):
    # | TRADING CODE | LTP* | HIGH | LOW | CLOSEP* | YCP* | CHANGE
      | TRADE | VALUE (mn) | VOLUME
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import certifi
import requests
from bs4 import BeautifulSoup

from config import AppConfig

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# TLS: dsebd.org omits its intermediate CA from the handshake. We ship
# that intermediate and append it to certifi's roots so verification
# stays fully enabled (same approach as the V1 single-stock scraper).
# ----------------------------------------------------------------------
_EXTRA_CA_FILE = (
    Path(__file__).resolve().parent / "certs" / "sectigo-dv-r36-intermediate.pem"
)
_ca_bundle_cache: Optional[str] = None


def _ca_bundle_path() -> str:
    global _ca_bundle_cache
    if _ca_bundle_cache is not None:
        return _ca_bundle_cache
    bundle = certifi.where()
    if _EXTRA_CA_FILE.exists():
        try:
            combined = Path(tempfile.gettempdir()) / "dse_market_ca_bundle.pem"
            combined.write_text(
                Path(bundle).read_text(encoding="utf-8")
                + "\n"
                + _EXTRA_CA_FILE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            bundle = str(combined)
        except OSError as exc:
            logger.warning("Could not build combined CA bundle (%s); using certifi.", exc)
    _ca_bundle_cache = bundle
    return bundle


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PRICE_SANITY_MAX = 1_000_000.0


# ----------------------------------------------------------------------
# Lightweight, heuristic sector inference.
# The scroll page does not expose sector/company name, so we derive a
# best-effort sector from well-known trading-code patterns. This powers
# the sector filter on the overview; it is intentionally conservative.
# ----------------------------------------------------------------------
_SECTOR_RULES: List[tuple] = [
    (re.compile(r"MF$|MUTUAL", re.I), "Mutual Fund"),
    (re.compile(r"BANK$|^.*BANK", re.I), "Bank"),
    (re.compile(r"(LIFE|INSUR|INS)$|LIFE", re.I), "Insurance"),
    (re.compile(r"(FIN|LEAS|INVEST|IDLC|FINANCE)", re.I), "NBFI / Finance"),
    (re.compile(r"(PHARMA|PHAR|LAB|HEALTH|MEDIC)", re.I), "Pharma & Health"),
    (re.compile(r"(TEX|TEXT|SPIN|YARN|FAB|KNIT|DENIM)", re.I), "Textile"),
    (re.compile(r"(CEMENT|CEM)", re.I), "Cement"),
    (re.compile(r"(FUEL|POWER|ENERGY|GAS|PETRO|OIL|SOLAR|ELECTR)", re.I), "Fuel & Power"),
    (re.compile(r"(FOOD|FOODS|SUGAR|MILK|OIL|BEVER|TEA)", re.I), "Food & Allied"),
    (re.compile(r"(CERAMIC|CERA|GLASS|TILE)", re.I), "Ceramics"),
    (re.compile(r"(TEL|GP$|BL$|NET|IT$|TECH|SOFT|DATA|ONLINE)", re.I), "Telecom & IT"),
    (re.compile(r"(JUTE)", re.I), "Jute"),
    (re.compile(r"(PAPER|PRINT)", re.I), "Paper & Printing"),
    (re.compile(r"(TANNERY|LEATHER|FOOTWEAR|SHOE|BATA)", re.I), "Tannery"),
    (re.compile(r"(CARGO|SHIP|TRANS|AIR|PORT)", re.I), "Travel & Transport"),
]


def infer_sector(code: str) -> str:
    """Best-effort sector for a trading code (heuristic, not authoritative)."""
    for pattern, sector in _SECTOR_RULES:
        if pattern.search(code):
            return sector
    return "General / Other"


def _to_float(text: str) -> Optional[float]:
    """'146.70' / '1,234.5' / '--' -> float | None."""
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("+", "").strip()
    if cleaned in ("", "-", "--", "N/A", "n/a"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_int(text: str) -> Optional[int]:
    value = _to_float(text)
    return int(value) if value is not None else None


@dataclass
class StockQuote:
    """One row of the latest-share-price table."""

    index: int                       # row number on the page (1..N)
    code: str                        # trading code, e.g. "OLYMPIC"
    ltp: Optional[float] = None      # last traded price
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None    # CLOSEP* (today's closing price)
    ycp: Optional[float] = None      # yesterday's closing price (prev close)
    change: Optional[float] = None   # absolute change vs YCP
    trades: Optional[int] = None     # number of trades
    value_mn: Optional[float] = None  # turnover, millions BDT
    volume: Optional[int] = None     # shares traded
    sector: str = ""
    name: str = ""                   # company name (not on this page)
    captured_at: datetime = field(default_factory=datetime.now)

    @property
    def change_pct(self) -> Optional[float]:
        """Percentage change vs yesterday's close."""
        if self.change is not None and self.ycp not in (None, 0):
            return self.change / self.ycp * 100.0
        if (self.ltp is not None and self.ycp not in (None, 0)):
            return (self.ltp - self.ycp) / self.ycp * 100.0
        return None

    @property
    def direction(self) -> str:
        c = self.change
        if c is None:
            return "flat"
        if c > 1e-9:
            return "up"
        if c < -1e-9:
            return "down"
        return "flat"

    @property
    def display_name(self) -> str:
        return self.name or self.code

    def to_row(self) -> Dict[str, object]:
        """Flat dict for DataFrames / DB upserts."""
        return {
            "index": self.index,
            "code": self.code,
            "ltp": self.ltp,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "ycp": self.ycp,
            "change": self.change,
            "change_pct": self.change_pct,
            "trades": self.trades,
            "value_mn": self.value_mn,
            "volume": self.volume,
            "sector": self.sector,
        }


@dataclass
class MarketSnapshot:
    """Outcome of one whole-market scrape."""

    success: bool
    quotes: List[StockQuote] = field(default_factory=list)
    error: str = ""
    captured_at: datetime = field(default_factory=datetime.now)
    method: str = "table"

    @property
    def count(self) -> int:
        return len(self.quotes)


class MarketScraper:
    """Fetches and parses the whole DSE latest-share-price table."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._session.verify = _ca_bundle_path()

    # ------------------------------------------------------------------
    def fetch_all(self) -> MarketSnapshot:
        """Fetch + parse the full market with retries. Never raises."""
        last_error = "unknown error"
        for attempt in range(1, self.cfg.max_retries_per_scrape + 1):
            html, err = self._get_html()
            if html:
                snap = self._parse(html)
                if snap.success and snap.count > 0:
                    return snap
                last_error = snap.error or "no rows parsed"
            else:
                last_error = err
            logger.warning(
                "Market scrape attempt %d/%d failed: %s",
                attempt, self.cfg.max_retries_per_scrape, last_error,
            )
            time.sleep(min(2 * attempt, 8))
        return MarketSnapshot(success=False, error=last_error)

    # ------------------------------------------------------------------
    def _get_html(self) -> tuple[Optional[str], str]:
        try:
            resp = self._session.get(
                self.cfg.scrape_url, timeout=self.cfg.request_timeout_seconds
            )
            resp.raise_for_status()
            if len(resp.text) < 2000:
                return None, "Response suspiciously small (possible block page)"
            return resp.text, ""
        except requests.exceptions.Timeout:
            return None, "HTTP timeout"
        except requests.exceptions.ConnectionError as exc:
            return None, f"Connection error: {exc}"
        except requests.exceptions.RequestException as exc:
            return None, f"HTTP error: {exc}"

    # ------------------------------------------------------------------
    def _parse(self, html: str) -> MarketSnapshot:
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # The data table is the one with the most <tr> rows whose header
        # contains "TRADING CODE". Be tolerant of layout changes.
        best_rows: List = []
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 10:
                continue
            header_text = " ".join(
                c.get_text(strip=True).upper()
                for c in rows[0].find_all(["td", "th"])
            )
            if "TRADING CODE" in header_text and "LTP" in header_text:
                if len(rows) > len(best_rows):
                    best_rows = rows

        if not best_rows:
            # Fallback: simply pick the largest table.
            tables = soup.find_all("table")
            if not tables:
                return MarketSnapshot(success=False, error="No tables found in page")
            best_rows = max(tables, key=lambda t: len(t.find_all("tr"))).find_all("tr")

        quotes: List[StockQuote] = []
        now = datetime.now()
        seen: set[str] = set()
        for row in best_rows:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 11:
                continue
            code = cells[1].strip().upper()
            # Skip header / non-data rows.
            if not code or code in ("TRADING CODE", "") or code in seen:
                continue
            if not re.match(r"^[A-Z0-9]", code):
                continue
            idx = _to_int(cells[0]) or (len(quotes) + 1)
            ltp = _to_float(cells[2])
            if ltp is not None and ltp > PRICE_SANITY_MAX:
                continue
            quote = StockQuote(
                index=idx,
                code=code,
                ltp=ltp,
                high=_to_float(cells[3]),
                low=_to_float(cells[4]),
                close=_to_float(cells[5]),
                ycp=_to_float(cells[6]),
                change=_to_float(cells[7]),
                trades=_to_int(cells[8]),
                value_mn=_to_float(cells[9]),
                volume=_to_int(cells[10]),
                sector=infer_sector(code),
                captured_at=now,
            )
            quotes.append(quote)
            seen.add(code)

        if not quotes:
            return MarketSnapshot(
                success=False, error="Parsed table but found 0 valid stock rows"
            )
        logger.info("Market scrape OK: %d stocks", len(quotes))
        return MarketSnapshot(success=True, quotes=quotes, captured_at=now)
