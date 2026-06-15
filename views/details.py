"""
views/details.py
----------------
Stock Details — the deep-dive analytics view.

Renders the full breakdown (basic info, price data, trading activity,
market-summary panel and professional charts) for any chosen stock. The
stock can be pre-selected from a dashboard card (via session_state) or
picked here from a searchable list. Auto-refreshes live.
"""

from __future__ import annotations

import streamlit as st

from components.detail import render_stock_detail
from runtime import flash, get_monitor

monitor = get_monitor()

quotes = monitor.all_quotes()
if not quotes:
    st.warning("Market data is still loading — use **⚡ Refresh now** in the sidebar.")
    st.stop()

idx_map = {q.code: q.index for q in quotes}
all_codes = sorted(idx_map, key=lambda c: idx_map[c])

# Resolve the initial code: card click (detail_code) > first selected > first listed.
default_code = st.session_state.get("detail_code")
if default_code not in idx_map:
    sel = monitor.get_selected()
    default_code = sel[0] if sel else all_codes[0]

c1, c2, c3 = st.columns([3, 1, 1])
code = c1.selectbox(
    "Choose a stock",
    options=all_codes,
    index=all_codes.index(default_code),
    format_func=lambda c: f"{idx_map.get(c, '?')}. {c}",
    key="detail_pick",
)
st.session_state["detail_code"] = code

with c2:
    st.write("")
    # Reflect dashboard membership (the selection this button toggles) —
    # NOT the broader tracked set, which also includes watchlists and alert
    # rules and would leave the button stuck on "Tracked".
    on_dashboard = code in monitor.get_selected()
    if on_dashboard:
        if st.button("★ Tracked", width="stretch",
                     help="On your dashboard — click to remove"):
            monitor.remove_selected(code)
            flash(f"{code} untracked", "☆")
            st.rerun()
    else:
        if st.button("☆ Track", type="primary", width="stretch",
                     help="Add to your dashboard (enables history + charts)"):
            monitor.add_selected(code)
            flash(f"{code} tracked", "★")
            st.rerun()
with c3:
    st.write("")
    if st.button("⚡ Refresh", width="stretch"):
        monitor.refresh_now()
        flash("Prices refreshed", "⚡")
        st.rerun()


@st.fragment(run_every="12s")
def live_detail() -> None:
    render_stock_detail(monitor, code)


live_detail()
