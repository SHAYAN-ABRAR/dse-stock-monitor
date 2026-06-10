"""
utils.py
--------
Shared helpers: timezone-aware clock, trading-hours logic, logging setup.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, time as dtime
from typing import Tuple
from zoneinfo import ZoneInfo

from config import AppConfig

# 12-hour display format used everywhere in the UI and WhatsApp messages.
DHAKA_FMT = "%Y-%m-%d %I:%M:%S %p"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once (idempotent)."""
    root = logging.getLogger()
    if root.handlers:  # already configured (Streamlit reruns the script)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)


def now_dhaka(cfg: AppConfig) -> datetime:
    """Current timezone-aware datetime in Asia/Dhaka (or configured tz)."""
    return datetime.now(ZoneInfo(cfg.timezone))


def parse_hhmm(value: str) -> dtime:
    """Parse 'HH:MM' into a datetime.time, falling back to midnight."""
    try:
        hour, minute = value.strip().split(":")
        return dtime(int(hour), int(minute))
    except (ValueError, AttributeError):
        return dtime(0, 0)


def fmt_hhmm_12(value: str) -> str:
    """'14:30' -> '2:30 PM' (for displaying configured trading hours)."""
    return parse_hhmm(value).strftime("%I:%M %p").lstrip("0")


def is_trading_hours(cfg: AppConfig) -> Tuple[bool, str]:
    """
    Return (open?, human-readable reason) for the configured market hours.

    DSE schedule: Sunday-Thursday. Continuous trading 10:00 AM - 2:20 PM,
    then a post-closing session 2:20 PM - 2:30 PM (Asia/Dhaka). Monitoring
    stays active through post-close because the LTP can still update.
    """
    now = now_dhaka(cfg)
    start = parse_hhmm(cfg.trading_start)
    cont_end = parse_hhmm(cfg.trading_continuous_end)
    end = parse_hhmm(cfg.trading_end)

    start_12 = fmt_hhmm_12(cfg.trading_start)
    cont_end_12 = fmt_hhmm_12(cfg.trading_continuous_end)
    end_12 = fmt_hhmm_12(cfg.trading_end)
    now_12 = now.strftime("%I:%M %p").lstrip("0")

    if now.weekday() not in cfg.trading_days:
        return False, f"Market closed today ({now.strftime('%A')})"
    if now.time() < start:
        return False, f"Market opens at {start_12} (now {now_12})"
    if now.time() > end:
        return False, f"Market closed at {end_12} (now {now_12})"
    if now.time() >= cont_end:
        return True, f"Post-closing session ({cont_end_12} - {end_12} BDT)"
    return True, f"Market open ({start_12} - {cont_end_12} BDT · post-close till {end_12})"


def fmt_ts(dt: datetime | None) -> str:
    """Format a datetime for display; em-dash when missing."""
    return dt.strftime(DHAKA_FMT) if dt else "—"


def normalize_whatsapp_number(raw: str) -> str:
    """
    Convert any common way of writing a number to international format
    (no 'whatsapp:' prefix):

        'whatsapp:+8801712345678' -> '+8801712345678'
        '8801712345678'           -> '+8801712345678'
        '01712345678'  (BD local) -> '+8801712345678'
        '008801712345678'         -> '+8801712345678'

    A local number starting with a single '0' is assumed to be
    Bangladeshi: the leading 0 is REPLACED by country code +880
    (Twilio rejects '+0...' as invalid — error 21211).
    """
    number = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if number.lower().startswith("whatsapp:"):
        number = number[len("whatsapp:"):]
    number = number.lstrip("+")
    if number.startswith("00"):          # international dialing prefix
        number = number[2:]
    elif number.startswith("0"):         # local BD format, e.g. 01670...
        number = "880" + number[1:]
    return "+" + number if number else ""


def is_valid_whatsapp_number(number: str) -> bool:
    """
    True for international format: '+' then 8-15 digits, where the
    first digit is 1-9 (a country code can never start with 0).
    """
    return bool(re.fullmatch(r"\+[1-9]\d{7,14}", number))
