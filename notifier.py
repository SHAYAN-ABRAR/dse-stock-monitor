"""
notifier.py
-----------
WhatsApp notifications via the Twilio WhatsApp API.

IMPORTANT: This module sends WhatsApp MESSAGES ONLY. It deliberately
contains no Twilio Voice / phone-call functionality of any kind.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import AppConfig

logger = logging.getLogger(__name__)

# Twilio exception messages embed terminal colour codes (e.g. "\x1b[31m")
# that render as garbage like "[31m[49m" in the dashboard -- strip them.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_error(exc: Exception) -> str:
    return _ANSI_RE.sub("", str(exc)).strip()


@dataclass
class NotifyResult:
    """Outcome of a notification attempt."""

    sent: bool
    message: str = ""
    error: str = ""
    sid: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


def _ensure_whatsapp_prefix(number: str) -> str:
    """Twilio requires the 'whatsapp:' prefix on both numbers."""
    number = number.strip()
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


class WhatsAppNotifier:
    """Thin, fault-tolerant wrapper around the Twilio WhatsApp message API."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._client = None
        if cfg.twilio_configured:
            try:
                from twilio.rest import Client

                self._client = Client(cfg.twilio_account_sid, cfg.twilio_auth_token)
            except ImportError:
                logger.error("twilio package not installed; notifications disabled.")
            except Exception as exc:
                logger.error("Failed to initialise Twilio client: %s", exc)
        else:
            logger.warning("Twilio not fully configured; WhatsApp alerts disabled.")

    # ------------------------------------------------------------------
    @property
    def ready(self) -> bool:
        return self._client is not None

    def send(self, body: str) -> NotifyResult:
        """Send a WhatsApp message; never raises."""
        if not self.ready:
            return NotifyResult(sent=False, message=body,
                                error="Twilio not configured")
        try:
            msg = self._client.messages.create(
                from_=_ensure_whatsapp_prefix(self.cfg.twilio_whatsapp_number),
                to=_ensure_whatsapp_prefix(self.cfg.recipient_whatsapp_number),
                body=body,
            )
            logger.info("WhatsApp sent (sid=%s)", msg.sid)
            return NotifyResult(sent=True, message=body, sid=msg.sid or "")
        except Exception as exc:
            logger.error("WhatsApp send failed: %s", exc)
            return NotifyResult(sent=False, message=body, error=_clean_error(exc))

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------
    def send_target_alert(self, price: float, timestamp: str,
                          ai_note: Optional[str] = None) -> NotifyResult:
        """Alert: price entered the target range."""
        body = (
            f"\U0001F514 DSE Alert: {self.cfg.trading_code} LTP = {price}\n"
            f"Condition: {self.cfg.target_min_price:g}-{self.cfg.target_max_price:g}\n"
            f"Time: {timestamp}\n"
            f"AI Note: {ai_note or 'No anomaly detected'}"
        )
        return self.send(body)

    def send_anomaly_alert(self, price: float, timestamp: str,
                           ai_note: str) -> NotifyResult:
        """Alert: AI detected abnormal price movement (sent independently)."""
        body = (
            f"⚠️ DSE AI Anomaly: {self.cfg.trading_code} LTP = {price}\n"
            f"Condition: {self.cfg.target_min_price:g}-{self.cfg.target_max_price:g}\n"
            f"Time: {timestamp}\n"
            f"AI Note: {ai_note}"
        )
        return self.send(body)

    def send_error_alert(self, error: str, timestamp: str) -> NotifyResult:
        """Alert: scraping failed repeatedly; monitoring auto-paused."""
        body = (
            f"\U0001F6A8 DSE Monitor ERROR\n"
            f"Stock: {self.cfg.trading_code}\n"
            f"Scraping failed {self.cfg.max_consecutive_failures} consecutive times.\n"
            f"Monitoring has been PAUSED automatically.\n"
            f"Last error: {error}\n"
            f"Time: {timestamp}"
        )
        return self.send(body)
