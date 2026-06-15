"""
views/alerts.py
---------------
Alerts — configure per-stock price alert rules and review the alert log.

Rules are evaluated every refresh cycle while live monitoring is on; a
match fires a WhatsApp message (Twilio) and is recorded. A per-rule
cooldown prevents repeated alerts for the same condition.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from market_monitor import rule_condition_text, rule_matches
from runtime import (confirm_action, flash, get_monitor, hero, pill,
                     request_confirm)
from utils import fmt_money

monitor = get_monitor()

hero("Alerts",
     "Set price-threshold rules · get instant WhatsApp notifications when they fire")

quotes = monitor.all_quotes()
if not quotes:
    st.warning("Market data is still loading — use **⚡ Refresh now** in the sidebar.")
    st.stop()

idx_map = {q.code: q.index for q in quotes}
all_codes = sorted(idx_map, key=lambda c: idx_map[c])

if not monitor.notifier.ready:
    st.markdown(
        '<div class="error-banner">⚠️ WhatsApp is not configured yet — rules will '
        'still trigger and be logged, but no message can be sent. Open '
        '<b>Settings</b> to add your Twilio credentials.</div>',
        unsafe_allow_html=True)

# ======================================================================
# Create an alert rule
# ======================================================================
st.markdown('<div class="section-title">➕ New Price Alert</div>',
            unsafe_allow_html=True)

with st.container(border=True):
    r1, r2, r3 = st.columns([2, 2, 2])
    default_code = st.session_state.get("detail_code")
    code = r1.selectbox(
        "Stock", options=all_codes,
        index=all_codes.index(default_code) if default_code in idx_map else 0,
        format_func=lambda c: f"{idx_map.get(c, '?')}. {c}", key="al_code")
    condition = r2.selectbox(
        "Condition", options=["above", "below", "range", "outside"],
        format_func=lambda c: {
            "above": "LTP rises to / above",
            "below": "LTP falls to / below",
            "range": "LTP enters a band",
            "outside": "LTP exits a band",
        }[c], key="al_cond")
    q = monitor.get_quote(code)
    current = q.ltp if q else 0.0
    r3.markdown(f"**Current LTP**\n\n### {fmt_money(current)} BDT")

    v1, v2, v3 = st.columns([2, 2, 2])
    min_price = max_price = None
    if condition == "above":
        min_price = v1.number_input("Trigger when LTP ≥", value=float(current or 0),
                                    step=0.5, format="%.2f", key="al_above")
    elif condition == "below":
        max_price = v1.number_input("Trigger when LTP ≤", value=float(current or 0),
                                    step=0.5, format="%.2f", key="al_below")
    else:
        lo = v1.number_input("Lower bound", value=float((current or 1) * 0.97),
                            step=0.5, format="%.2f", key="al_lo")
        hi = v2.number_input("Upper bound", value=float((current or 1) * 1.03),
                            step=0.5, format="%.2f", key="al_hi")
        min_price, max_price = min(lo, hi), max(lo, hi)
    cooldown = v3.number_input("Cooldown (minutes)", min_value=1, max_value=240,
                              value=10, step=1, key="al_cd",
                              help="Minimum gap between repeated alerts for "
                                   "this rule.")
    note = st.text_input("Note (optional)", placeholder="e.g. buy zone",
                        key="al_note")

    if st.button("🔔 Create alert", type="primary", width="stretch"):
        monitor.repo.add_rule(code, condition, min_price, max_price,
                              cooldown_sec=int(cooldown) * 60, note=note.strip())
        # Tracking the stock ensures its history + rule are evaluated.
        monitor.add_selected(code)
        flash(f"Alert created for {code}", "🔔")
        st.rerun()

# ======================================================================
# Active rules
# ======================================================================
st.markdown('<div class="section-title">🔔 Active Alert Rules</div>',
            unsafe_allow_html=True)

rules = monitor.repo.get_rules()

# Confirmation modal for a pending rule deletion (flag-driven so its buttons
# are processed on the rerun that handles the click).
if (rid_del := st.session_state.get("_rule_delete")) is not None:
    _r = next((r for r in rules if r["id"] == rid_del), None)
    confirm_action(
        "Delete this alert rule?",
        (f"{_r['code']} · {rule_condition_text(_r)}. " if _r else "")
        + "This cannot be undone.",
        on_confirm=lambda rid=rid_del: monitor.repo.delete_rule(rid),
        clear_key="_rule_delete",
        confirm_label="🗑 Yes, delete",
        success_message="Alert rule deleted", success_icon="🗑",
    )

if not rules:
    st.info("No alert rules yet. Create one above — e.g. *OLYMPIC LTP ≥ 145*.")
else:
    for rule in rules:
        rcode = rule["code"]
        rq = monitor.get_quote(rcode)
        ltp = rq.ltp if rq else None
        matched = rule_matches(rule, ltp)
        with st.container(border=True):
            c = st.columns([2, 3, 2, 1.4, 1])
            c[0].markdown(f"**{rcode}** &nbsp;#{idx_map.get(rcode, '?')}")
            c[1].markdown(f"`{rule_condition_text(rule)}`"
                          + (f"  · _{rule['note']}_" if rule.get("note") else ""))
            status = (pill("● IN RANGE", "green") if matched
                      else pill("○ waiting", "blue"))
            ltp_str = fmt_money(ltp) if ltp is not None else "—"
            c[2].markdown(f"LTP {ltp_str}<br>{status}", unsafe_allow_html=True)
            enabled = c[3].toggle("Enabled", value=bool(rule["enabled"]),
                                  key=f"en_{rule['id']}")
            if enabled != bool(rule["enabled"]):
                monitor.repo.set_rule_enabled(rule["id"], enabled)
                st.rerun()
            if c[4].button("🗑", key=f"delr_{rule['id']}", width="stretch",
                           help="Delete this rule"):
                request_confirm("_rule_delete", rule["id"])
            if rule.get("last_fired_at"):
                c[0].caption(f"last fired {rule['last_fired_at']}")

# ======================================================================
# Alert history
# ======================================================================
st.markdown('<div class="section-title">🗂 Alert History</div>',
            unsafe_allow_html=True)
hist = monitor.repo.recent_alerts(limit=200)
if hist.empty:
    st.caption("No alerts fired yet.")
else:
    h = hist.copy()
    h["sent"] = h["sent"].map({1: "✅ sent", 0: "❌ failed"})
    h["ts"] = pd.to_datetime(h["ts"]).dt.strftime("%Y-%m-%d %I:%M:%S %p")
    h = h.rename(columns={"ts": "Time", "code": "Stock", "alert_type": "Type",
                          "price": "LTP", "message": "Message", "sent": "Status",
                          "error": "Error"})
    st.dataframe(h, width="stretch", hide_index=True, height=340,
                 column_config={"LTP": st.column_config.NumberColumn(format="%.2f")})
