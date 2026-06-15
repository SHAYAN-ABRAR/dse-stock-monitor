"""
views/settings.py
-----------------
Settings — WhatsApp (Twilio) notification setup, a one-click test
message, refresh cadence, and platform / data status.
"""

from __future__ import annotations

import re

import streamlit as st

from runtime import flash, get_monitor, hero
from utils import (fmt_hhmm_12, is_valid_whatsapp_number,
                   normalize_whatsapp_number, now_dhaka)

monitor = get_monitor()
cfg = monitor.cfg

hero("Settings",
     "WhatsApp alerts · Twilio credentials · refresh cadence · data status")

# ======================================================================
# WhatsApp (Twilio)
# ======================================================================
st.markdown('<div class="section-title">📱 WhatsApp Notifications (Twilio)</div>',
            unsafe_allow_html=True)

recipient_now = normalize_whatsapp_number(cfg.recipient_whatsapp_number)
sid_now = cfg.twilio_account_sid.strip()
sender_now = normalize_whatsapp_number(cfg.twilio_whatsapp_number)

with st.container(border=True):
    if cfg.twilio_configured:
        st.success("All credentials are saved on this device. The grey text in "
                   "each box shows the saved value — leave a field empty to "
                   "keep it.", icon="💾")
    else:
        st.info("Enter your Twilio credentials below to arm WhatsApp alerts. "
                "Get them free at console.twilio.com.", icon="🔐")
    st.caption("Alerts are sent **only** as WhatsApp messages (no calls/SMS). "
               "On the Twilio sandbox, the recipient must first send the "
               "`join <code>` message to the sandbox number.")

    with st.form("twilio_form", border=False, enter_to_submit=False):
        sid_ph = (f"Current: {sid_now[:6]}…{sid_now[-4:]}"
                  if cfg.twilio_configured else "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        sid_in = st.text_input("Account SID", value="", placeholder=sid_ph,
                               help="Starts with 'AC' followed by 32 characters.")
        token_in = st.text_input(
            "Auth Token", value="", type="password",
            placeholder="Current token saved (hidden)" if cfg.twilio_configured
            else "Paste your Auth Token",
            help="Hidden for security.")
        sender_in = st.text_input(
            "Twilio WhatsApp sender number", value="",
            placeholder=sender_now or "+14155238886",
            help="The number Twilio sends FROM. Sandbox default: +14155238886")
        recipient_in = st.text_input(
            "Send alerts to this WhatsApp number", value="",
            placeholder=recipient_now or "+8801XXXXXXXXX",
            help="The number that RECEIVES alerts, international format "
                 "e.g. +8801712345678.")
        saved = st.form_submit_button("💾 Save credentials", type="primary",
                                      width="stretch")

    if saved:
        sid_clean = sid_in.strip() or sid_now
        token_clean = token_in.strip() or cfg.twilio_auth_token.strip()
        sender_clean = normalize_whatsapp_number(sender_in) or sender_now
        recipient_clean = normalize_whatsapp_number(recipient_in) or recipient_now
        problems = []
        if not re.fullmatch(r"AC[0-9a-fA-F]{32}", sid_clean):
            problems.append("Account SID must be 'AC' + 32 characters.")
        if len(token_clean) < 16 or "your_auth_token" in token_clean.lower():
            problems.append("Auth Token looks invalid — paste the real token.")
        if not is_valid_whatsapp_number(sender_clean):
            problems.append("Sender number must be international format, e.g. +14155238886.")
        if not is_valid_whatsapp_number(recipient_clean):
            problems.append("Recipient number must be international format, e.g. +8801712345678.")
        if problems:
            for p in problems:
                st.error(p)
        else:
            monitor.update_twilio_credentials(sid_clean, token_clean, sender_clean)
            ready = monitor.update_recipient_number(recipient_clean)
            flash("Credentials saved" + ("" if ready else " (check them)"),
                  "💾" if ready else "⚠️")
            st.rerun()

    if monitor.notifier.ready:
        st.success(f"WhatsApp armed · alerts go to {recipient_now}", icon="✅")
        if st.button("📨 Send test WhatsApp message"):
            res = monitor.notifier.send(
                f"✅ Test from DSE Terminal — {now_dhaka(cfg):%Y-%m-%d %I:%M:%S %p}")
            if res.sent:
                st.success(f"Sent! Message SID: {res.sid}")
            else:
                st.error(f"Failed: {res.error}")
    else:
        st.warning("WhatsApp not yet configured — alerts are disabled.", icon="⚠️")

# ======================================================================
# Platform settings + status
# ======================================================================
left, right = st.columns(2)

with left:
    st.markdown('<div class="section-title">⏱ Refresh & Market Hours</div>',
                unsafe_allow_html=True)
    with st.container(border=True):
        interval = st.number_input(
            "Market refresh interval (seconds)", min_value=30, max_value=600,
            step=15, value=int(cfg.refresh_interval_seconds), key="set_interval")
        if int(interval) != cfg.refresh_interval_seconds:
            monitor.update_refresh_interval(int(interval))
            flash(f"Refresh interval → {int(interval)}s", "⏱")
        st.markdown("**Trading hours (Asia/Dhaka)**")
        st.code(
            f"Sun–Thu\n"
            f"Continuous : {fmt_hhmm_12(cfg.trading_start)} – {fmt_hhmm_12(cfg.trading_continuous_end)}\n"
            f"Post-close : {fmt_hhmm_12(cfg.trading_continuous_end)} – {fmt_hhmm_12(cfg.trading_end)}")
        st.caption("AI anomaly detection: "
                   + ("enabled ✅" if cfg.ai_enabled else "disabled"))

with right:
    st.markdown('<div class="section-title">🗄 Data & Storage</div>',
                unsafe_allow_html=True)
    with st.container(border=True):
        stats = monitor.repo.stats()
        snap = monitor.snapshot()
        st.markdown(f"""
        - **Stocks in snapshot:** {stats['stocks']}
        - **History rows stored:** {stats['history_rows']:,}
        - **Alert rules:** {stats['rules']}
        - **Alerts sent:** {stats['alerts_sent']}
        - **Tracked stocks:** {len(monitor.tracked_codes())}
        - **Last refresh:** {snap['last_refresh_time'].strftime('%I:%M:%S %p') if snap['last_refresh_time'] else '—'}
        """)
        st.caption(f"SQLite database: `{cfg.market_db_path}`")
        st.caption(f"History retention: {cfg.history_retention_days} days")
        if snap["consecutive_errors"] > 0:
            st.warning(f"Last refresh error: {snap['last_error']}", icon="⚠️")
