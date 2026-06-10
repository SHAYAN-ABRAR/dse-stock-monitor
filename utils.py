"""
utils.py
--------
Shared helpers: timezone-aware clock, trading-hours logic, logging setup.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, time as dtime
from typing import Tuple
from zoneinfo import ZoneInfo

from config import AppConfig

DHAKA_FMT = "%Y-%m-%d %H:%M:%S"


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


def is_trading_hours(cfg: AppConfig) -> Tuple[bool, str]:
    """
    Return (open?, human-readable reason) for the configured market hours.

    Default: Monday-Thursday, 10:00-14:30 Asia/Dhaka.
    """
    now = now_dhaka(cfg)
    start = parse_hhmm(cfg.trading_start)
    end = parse_hhmm(cfg.trading_end)

    if now.weekday() not in cfg.trading_days:
        return False, f"Market closed today ({now.strftime('%A')})"
    if now.time() < start:
        return False, f"Market opens at {cfg.trading_start} (now {now.strftime('%H:%M')})"
    if now.time() > end:
        return False, f"Market closed at {cfg.trading_end} (now {now.strftime('%H:%M')})"
    return True, f"Market open ({cfg.trading_start}-{cfg.trading_end} BDT)"


def fmt_ts(dt: datetime | None) -> str:
    """Format a datetime for display; em-dash when missing."""
    return dt.strftime(DHAKA_FMT) if dt else "—"
