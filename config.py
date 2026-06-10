"""
config.py
---------
Centralised configuration management for the DSE Stock Monitor.

Configuration is loaded (in order of precedence):
    1. Streamlit secrets  (st.secrets)  -> for Streamlit Cloud deployment
    2. Environment variables (.env)     -> for local / server deployment
    3. config.json                      -> non-secret defaults
    4. Hard-coded fallback defaults

Secrets (Twilio credentials, phone numbers) should live in .env or
st.secrets. Non-secret tunables (price range, polling interval, trading
hours) can live in config.json and are editable at runtime from the UI.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from the project root (no-op if the file does not exist).
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

CONFIG_JSON_PATH = PROJECT_ROOT / "config.json"

# Settings changed from the dashboard at runtime (e.g. the recipient
# WhatsApp number) are persisted here and applied with HIGHEST
# precedence on startup -- they survive restarts and beat .env values.
USER_SETTINGS_PATH = PROJECT_ROOT / "user_settings.json"


def _load_user_settings() -> Dict[str, Any]:
    if USER_SETTINGS_PATH.exists():
        try:
            return json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not parse user_settings.json: %s", exc)
    return {}


def save_user_setting(key: str, value: Any) -> None:
    """Persist a dashboard-made setting so it survives app restarts."""
    settings = _load_user_settings()
    settings[key] = value
    try:
        USER_SETTINGS_PATH.write_text(
            json.dumps(settings, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Could not write user_settings.json: %s", exc)


def _streamlit_secret(key: str) -> Optional[str]:
    """Read a key from st.secrets without crashing outside Streamlit."""
    try:
        import streamlit as st  # imported lazily on purpose

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # No secrets.toml, or not running inside Streamlit -- both fine.
        pass
    return None


def _get(key: str, default: Any = None, json_cfg: Optional[Dict[str, Any]] = None) -> Any:
    """Resolve a config key using the precedence chain."""
    value = _streamlit_secret(key)
    if value is not None:
        return value
    value = os.getenv(key)
    if value is not None:
        return value
    if json_cfg and key in json_cfg:
        return json_cfg[key]
    return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AppConfig:
    """Strongly-typed application configuration."""

    # --- Stock / target ---
    trading_code: str = "OLYMPIC"
    target_min_price: float = 143.0
    target_max_price: float = 145.0

    # --- Scraping ---
    scrape_url: str = "https://www.dsebd.org/latest_share_price_scroll_l.php"
    polling_interval_seconds: int = 120          # every 2 minutes
    request_timeout_seconds: int = 25
    max_retries_per_scrape: int = 3
    max_consecutive_failures: int = 3            # then alert + auto-pause

    # --- Trading hours (Asia/Dhaka) ---
    # DSE: Sun-Thu. Continuous trading 10:00-14:20, then a post-closing
    # session 14:20-14:30. Monitoring runs through post-close (LTP can
    # still print there), so trading_end is 14:30.
    timezone: str = "Asia/Dhaka"
    trading_days: tuple = (6, 0, 1, 2, 3)        # Sun=6, Mon=0 ... Thu=3
    trading_start: str = "10:00"
    trading_continuous_end: str = "14:20"        # display only
    trading_end: str = "14:30"

    # --- AI / anomaly detection ---
    ai_enabled: bool = True
    ai_history_size: int = 20                    # keep last N prices
    ai_spike_threshold_pct: float = 2.0          # >2% move within one poll

    # --- Notifications (Twilio WhatsApp ONLY -- no voice/calls) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""             # e.g. "whatsapp:+14155238886"
    recipient_whatsapp_number: str = ""          # e.g. "whatsapp:+8801XXXXXXXXX"
    realert_on_same_price: bool = False          # dedupe identical-price alerts
    alert_cooldown_seconds: int = 600            # min gap between target alerts

    # --- Storage ---
    db_path: str = str(PROJECT_ROOT / "dse_monitor.db")
    csv_log_path: str = str(PROJECT_ROOT / "scrape_log.csv")

    # ------------------------------------------------------------------
    @property
    def twilio_configured(self) -> bool:
        """
        True when all four Twilio fields are present AND none of them is
        an obvious placeholder copied from .env.example.
        """
        values = [
            self.twilio_account_sid,
            self.twilio_auth_token,
            self.twilio_whatsapp_number,
            self.recipient_whatsapp_number,
        ]
        if not all(values):
            return False
        joined = " ".join(values).lower()
        placeholders = ("xxxx", "your_auth_token", "your_account_sid")
        return not any(hint in joined for hint in placeholders)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Dict representation with secrets masked (for display/debug)."""
        data = asdict(self)
        for secret_key in ("twilio_account_sid", "twilio_auth_token"):
            if data.get(secret_key):
                data[secret_key] = data[secret_key][:4] + "..." + "****"
        return data


def load_config() -> AppConfig:
    """Build an AppConfig from secrets / env / config.json / defaults."""
    json_cfg: Dict[str, Any] = {}
    if CONFIG_JSON_PATH.exists():
        try:
            json_cfg = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not parse config.json: %s", exc)

    defaults = AppConfig()

    def g(key: str, default: Any) -> Any:
        return _get(key.upper(), _get(key, default, json_cfg), json_cfg)

    cfg = AppConfig(
        trading_code=str(g("trading_code", defaults.trading_code)),
        target_min_price=float(g("target_min_price", defaults.target_min_price)),
        target_max_price=float(g("target_max_price", defaults.target_max_price)),
        scrape_url=str(g("scrape_url", defaults.scrape_url)),
        polling_interval_seconds=int(g("polling_interval_seconds", defaults.polling_interval_seconds)),
        request_timeout_seconds=int(g("request_timeout_seconds", defaults.request_timeout_seconds)),
        max_retries_per_scrape=int(g("max_retries_per_scrape", defaults.max_retries_per_scrape)),
        max_consecutive_failures=int(g("max_consecutive_failures", defaults.max_consecutive_failures)),
        timezone=str(g("timezone", defaults.timezone)),
        trading_days=tuple(json_cfg.get("trading_days", defaults.trading_days)),
        trading_start=str(g("trading_start", defaults.trading_start)),
        trading_continuous_end=str(g("trading_continuous_end", defaults.trading_continuous_end)),
        trading_end=str(g("trading_end", defaults.trading_end)),
        ai_enabled=_as_bool(g("ai_enabled", defaults.ai_enabled)),
        ai_history_size=int(g("ai_history_size", defaults.ai_history_size)),
        ai_spike_threshold_pct=float(g("ai_spike_threshold_pct", defaults.ai_spike_threshold_pct)),
        twilio_account_sid=str(g("twilio_account_sid", "") or ""),
        twilio_auth_token=str(g("twilio_auth_token", "") or ""),
        twilio_whatsapp_number=str(g("twilio_whatsapp_number", "") or ""),
        recipient_whatsapp_number=str(g("recipient_whatsapp_number", "") or ""),
        realert_on_same_price=_as_bool(g("realert_on_same_price", defaults.realert_on_same_price)),
        alert_cooldown_seconds=int(g("alert_cooldown_seconds", defaults.alert_cooldown_seconds)),
        db_path=str(g("db_path", defaults.db_path)),
        csv_log_path=str(g("csv_log_path", defaults.csv_log_path)),
    )

    if cfg.target_min_price > cfg.target_max_price:
        logger.warning("target_min_price > target_max_price; swapping.")
        cfg.target_min_price, cfg.target_max_price = cfg.target_max_price, cfg.target_min_price

    # Dashboard-made overrides win over everything else.
    overrides = _load_user_settings()
    for key in ("recipient_whatsapp_number", "twilio_account_sid",
                "twilio_auth_token", "twilio_whatsapp_number"):
        if overrides.get(key):
            setattr(cfg, key, str(overrides[key]))
    if overrides.get("polling_interval_seconds"):
        try:
            cfg.polling_interval_seconds = max(60, int(overrides["polling_interval_seconds"]))
        except (TypeError, ValueError):
            pass

    return cfg
