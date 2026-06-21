"""
views/watchlists.py
-------------------
Watchlists — save, load, and delete named groups of stocks
("Banking", "High Volume", "Long-Term Investments", …). Loading a
watchlist populates the dashboard; every watchlist member is tracked
for history + alerts.
"""

from __future__ import annotations

import streamlit as st

from runtime import (confirm_action, flash, get_monitor, hero, pill,
                     request_confirm)
from utils import fmt_money

monitor = get_monitor()

hero("Watchlists",
     "Curate themed stock groups · load them onto your dashboard in one click")

quotes = monitor.all_quotes()
if not quotes:
    st.warning("Market data is still loading — use **⚡ Refresh now** in the sidebar.")
    st.stop()

idx_map = {q.code: q.index for q in quotes}
all_codes = sorted(idx_map, key=lambda c: idx_map[c])
watchlists = monitor.repo.get_watchlists()

# Confirmation modal for a pending watchlist deletion (opened from a flag so
# its buttons are processed on the rerun that handles the click).
if (wl_del := st.session_state.get("_wl_delete")) is not None:
    confirm_action(
        f"Delete the watchlist '{wl_del}'?",
        "This permanently deletes the watchlist. Your current dashboard "
        "selection is not affected.",
        on_confirm=lambda n=wl_del: monitor.repo.delete_watchlist(n),
        clear_key="_wl_delete",
        confirm_label="🗑 Yes, delete",
        success_message=f"Watchlist '{wl_del}' deleted", success_icon="🗑",
    )

# ======================================================================
# Create / update a watchlist
# ======================================================================
st.markdown('<div class="section-title">➕ Create or Update a Watchlist</div>',
            unsafe_allow_html=True)

with st.form("wl_form", border=True):
    f1, f2 = st.columns([1, 2])
    name = f1.text_input("Watchlist name", placeholder="e.g. Banking",
                         key="wl_name")
    preset = st.session_state.get("wl_edit_codes", [])
    codes = f2.multiselect(
        "Stocks", options=all_codes, default=preset,
        format_func=lambda c: f"{idx_map.get(c, '?')}. {c}",
        placeholder="Search and add stocks…", key="wl_codes")
    submitted = st.form_submit_button("💾 Save watchlist", type="primary",
                                      width="stretch")
    if submitted:
        if not name.strip():
            st.error("Please give the watchlist a name.")
        elif not codes:
            st.error("Add at least one stock.")
        else:
            monitor.repo.save_watchlist(name.strip(), codes)
            st.session_state.pop("wl_edit_codes", None)
            flash(f"Watchlist '{name.strip()}' saved", "⭐")
            st.rerun()

# ======================================================================
# Existing watchlists
# ======================================================================
st.markdown('<div class="section-title">⭐ Your Watchlists</div>',
            unsafe_allow_html=True)

if not watchlists:
    st.info("No watchlists yet. Create one above — for example a **Banking** "
            "list, a **High Volume** list, or **Long-Term Investments**.")
else:
    for wl_name, members in watchlists.items():
        live_members = [c for c in members if c in idx_map]
        with st.container(border=True):
            head = st.columns([3, 1, 1, 1])
            head[0].markdown(
                f"**{wl_name}** &nbsp; {pill(f'{len(live_members)} stocks', 'blue')}",
                unsafe_allow_html=True)
            if head[1].button("📥 Load", key=f"load_{wl_name}",
                              width="stretch",
                              help="Replace dashboard selection with this watchlist"):
                monitor.set_selected(live_members)
                flash(f"Loaded '{wl_name}' ({len(live_members)} stocks)", "📥")
                st.switch_page("views/dashboard.py")
            if head[2].button("➕ Add", key=f"add_{wl_name}",
                              width="stretch",
                              help="Add this watchlist to the current dashboard"):
                merged = list(dict.fromkeys(monitor.get_selected() + live_members))
                monitor.set_selected(merged)
                flash(f"Added '{wl_name}' ({len(live_members)} stocks)", "➕")
                st.rerun()
            if head[3].button("🗑 Delete", key=f"del_{wl_name}",
                              width="stretch"):
                request_confirm("_wl_delete", wl_name)

            # Member mini-table
            rows = ""
            for c in live_members:
                q = monitor.get_quote(c)
                if q is None:
                    continue
                d = q.direction
                color = {"up": "#10b981", "down": "#ef4444",
                         "flat": "var(--text-muted)"}[d]
                pct = q.change_pct
                pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                rows += (
                    f'<span style="display:inline-flex;gap:6px;align-items:center;'
                    f'background:var(--surface);border:1px solid var(--border);'
                    f'border-radius:999px;padding:4px 11px;margin:3px;">'
                    f'<b style="color:var(--text-strong);">{c}</b>'
                    f'<span style="color:var(--text-muted);">{fmt_money(q.ltp)}</span>'
                    f'<span style="color:{color};font-weight:700;">{pct_str}</span></span>'
                )
            st.markdown(f'<div style="margin-top:6px;">{rows}</div>',
                        unsafe_allow_html=True)
