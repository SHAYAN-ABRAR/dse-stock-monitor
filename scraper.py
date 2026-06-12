"""
scraper.py
----------
Scrapes the LTP (Last Traded Price) for a trading code from the DSE
"Latest Share Price" page.

Strategy (in order):
    1. requests + BeautifulSoup against the static HTML table.
    2. If the page appears dynamically rendered / table missing,
       automatically fall back to a headless browser
       (Playwright preferred, Selenium as a secondary option) when
       either library is installed.
    3. Last-resort fallback: scan ALL page text for the trading code and
       extract the nearest adjacent numeric value as the price.

Every scrape returns a structured ScrapeResult and never raises to the
caller -- failures are encoded in the result so the monitor loop can
retry / count consecutive errors without crashing.
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import certifi
import requests
from bs4 import BeautifulSoup

from config import AppConfig

logger = logging.getLogger(__name__)

# www.dsebd.org's server omits its intermediate CA certificate
# ("Sectigo Public Server Authentication CA DV R36") from the TLS
# handshake, so default certificate verification fails with
# CERTIFICATE_VERIFY_FAILED. We ship that intermediate with the app and
# append it to certifi's trust store so the chain can be completed --
# verification stays fully enabled.
_EXTRA_CA_FILE = Path(__file__).resolve().parent / "certs" / "sectigo-dv-r36-intermediate.pem"
_ca_bundle_cache: Optional[str] = None


def _ca_bundle_path() -> str:
    """Return a CA bundle path = certifi roots + bundled DSE intermediate."""
    global _ca_bundle_cache
    if _ca_bundle_cache is not None:
        return _ca_bundle_cache
    bundle = certifi.where()
    if _EXTRA_CA_FILE.exists():
        try:
            combined = Path(tempfile.gettempdir()) / "dse_monitor_ca_bundle.pem"
            combined.write_text(
                Path(bundle).read_text(encoding="utf-8")
                + "\n"
                + _EXTRA_CA_FILE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            bundle = str(combined)
        except OSError as exc:
            logger.warning(
                "Could not build combined CA bundle (%s); using certifi default.", exc
            )
    _ca_bundle_cache = bundle
    return bundle

# A sane price band used to validate extracted values (rejects volumes,
# percentages and obviously broken parses). Wide enough for any DSE stock.
PRICE_SANITY_MIN = 0.1
PRICE_SANITY_MAX = 100_000.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class ScrapeResult:
    """Structured outcome of a single scrape attempt."""

    success: bool
    price: Optional[float] = None
    trading_code: str = ""
    method: str = ""                 # "table" | "browser" | "text-fallback"
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    raw_row: Optional[List[str]] = None  # full table row for debugging


def _validate_price(value: float) -> bool:
    """Reject values that cannot plausibly be a share price."""
    return PRICE_SANITY_MIN <= value <= PRICE_SANITY_MAX


def _to_float(text: str) -> Optional[float]:
    """'146.70' / '1,234.5' -> float, else None."""
    try:
        return float(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


class DSEScraper:
    """Fetches and parses the DSE latest-share-price page."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._session.verify = _ca_bundle_path()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_price(self) -> ScrapeResult:
        """
        Fetch the LTP with retries. Tries the static-HTML path first and
        automatically escalates to a headless browser, then to a raw
        text scan. Never raises.
        """
        last_error = "unknown error"
        for attempt in range(1, self.cfg.max_retries_per_scrape + 1):
            result = self._fetch_once()
            if result.success:
                return result
            last_error = result.error
            logger.warning(
                "Scrape attempt %d/%d failed: %s",
                attempt, self.cfg.max_retries_per_scrape, result.error,
            )
            # Small backoff between retries (2s, 4s, ...)
            time.sleep(min(2 * attempt, 8))

        return ScrapeResult(
            success=False,
            trading_code=self.cfg.trading_code,
            error=f"All {self.cfg.max_retries_per_scrape} attempts failed. Last: {last_error}",
        )

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------
    def _fetch_once(self) -> ScrapeResult:
        """One full attempt: requests -> browser fallback -> text fallback."""
        html, err = self._get_html_requests()
        if html:
            result = self._parse_table(html, method="table")
            if result.success:
                return result
            # Table missing or code not found -> maybe dynamic rendering.
            logger.info("Static parse failed (%s); trying browser fallback.", result.error)
            browser_html = self._get_html_browser()
            if browser_html:
                result = self._parse_table(browser_html, method="browser")
                if result.success:
                    return result
                html = browser_html  # use richer DOM for the text fallback
            # Last resort: scan visible text near the trading code.
            return self._parse_text_fallback(html)

        # requests itself failed (network problem) -> try browser directly.
        browser_html = self._get_html_browser()
        if browser_html:
            result = self._parse_table(browser_html, method="browser")
            if result.success:
                return result
            return self._parse_text_fallback(browser_html)

        return ScrapeResult(
            success=False, trading_code=self.cfg.trading_code,
            error=err or "Could not retrieve page by any method",
        )

    def _get_html_requests(self) -> tuple[Optional[str], str]:
        """Plain HTTP fetch. Returns (html, error_message)."""
        try:
            resp = self._session.get(
                self.cfg.scrape_url, timeout=self.cfg.request_timeout_seconds
            )
            resp.raise_for_status()
            if len(resp.text) < 500:
                return None, "Response suspiciously small (possible block page)"
            return resp.text, ""
        except requests.exceptions.Timeout:
            return None, "HTTP timeout"
        except requests.exceptions.ConnectionError as exc:
            return None, f"Connection error: {exc}"
        except requests.exceptions.RequestException as exc:
            return None, f"HTTP error: {exc}"

    def _get_html_browser(self) -> Optional[str]:
        """
        Headless-browser fetch for dynamically rendered content.
        Uses Playwright if installed, else Selenium, else returns None.
        Both imports are optional so the app runs fine without them.
        """
        # --- Playwright -------------------------------------------------
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=HEADERS["User-Agent"])
                    page.goto(self.cfg.scrape_url,
                              timeout=self.cfg.request_timeout_seconds * 1000)
                    page.wait_for_load_state("networkidle", timeout=15_000)
                    return page.content()
                finally:
                    browser.close()
        except ImportError:
            pass
        except Exception as exc:  # browser crashed, timeout, etc.
            logger.warning("Playwright fallback failed: %s", exc)

        # --- Selenium ---------------------------------------------------
        try:
            from selenium import webdriver  # type: ignore
            from selenium.webdriver.chrome.options import Options  # type: ignore

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={HEADERS['User-Agent']}")
            driver = webdriver.Chrome(options=options)
            try:
                driver.set_page_load_timeout(self.cfg.request_timeout_seconds)
                driver.get(self.cfg.scrape_url)
                time.sleep(3)  # allow any JS to settle
                return driver.page_source
            finally:
                driver.quit()
        except ImportError:
            logger.debug("Neither Playwright nor Selenium installed; skipping browser fallback.")
        except Exception as exc:
            logger.warning("Selenium fallback failed: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------
    def _parse_table(self, html: str, method: str) -> ScrapeResult:
        """
        Parse the share-price table. Row layout on dsebd.org:
            # | TRADING CODE | LTP | HIGH | LOW | CLOSEP | YCP | CHANGE | ...
        We locate the row whose trading-code cell matches exactly, then
        take the cell immediately after it as the LTP.
        """
        code = self.cfg.trading_code.upper()
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]
            for idx, text in enumerate(cell_texts):
                if text.upper() == code:
                    # LTP is the column right after TRADING CODE.
                    if idx + 1 < len(cell_texts):
                        price = _to_float(cell_texts[idx + 1])
                        if price is not None and _validate_price(price):
                            return ScrapeResult(
                                success=True, price=price, trading_code=code,
                                method=method, raw_row=cell_texts,
                            )
                    return ScrapeResult(
                        success=False, trading_code=code, method=method,
                        error=f"Row found but LTP cell invalid: {cell_texts}",
                    )
        return ScrapeResult(
            success=False, trading_code=code, method=method,
            error=f"Trading code '{code}' not found in any table",
        )

    def _parse_text_fallback(self, html: Optional[str]) -> ScrapeResult:
        """
        Fallback: find any visible occurrence of the trading code in the
        page text and extract the nearest following number as the price.
        """
        code = self.cfg.trading_code.upper()
        if not html:
            return ScrapeResult(success=False, trading_code=code,
                                error="No HTML available for text fallback")
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        text = soup.get_text(separator=" ", strip=True)
        for match in re.finditer(re.escape(code), text, flags=re.IGNORECASE):
            # Look at the 80 chars after the code for the first decimal number.
            window = text[match.end(): match.end() + 80]
            for num_match in re.finditer(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+", window):
                price = _to_float(num_match.group())
                if price is not None and _validate_price(price):
                    logger.info("Text-fallback extracted %s = %s", code, price)
                    return ScrapeResult(
                        success=True, price=price, trading_code=code,
                        method="text-fallback",
                    )
        return ScrapeResult(
            success=False, trading_code=code, method="text-fallback",
            error=f"'{code}' not found anywhere in page text",
        )
