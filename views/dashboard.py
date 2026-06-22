"""
views/dashboard.py
------------------
My Dashboard — the multi-stock command centre.

A professional searchable multi-select (every DSE stock, shown as
"[index]. [code]") drives a responsive grid of live glassmorphic cards.
Each card auto-updates, opens the full analytics view, or can be removed
(with a confirmation prompt).
"""

from __future__ import annotations

import streamlit as st

from components.cards import render_cards
from runtime import (confirm_action, flash, get_monitor, hero, pill,
                     request_confirm)

monitor = get_monitor()
cfg = monitor.cfg

hero("My Dashboard",
     "Your selected stocks · live cards · one-click deep-dive analytics")

quotes = monitor.all_quotes()
if not quotes:
    st.warning("Market data is still loading — use **⚡ Refresh now** in the sidebar.")
    st.stop()

idx_map = {q.code: q.index for q in quotes}
all_codes = sorted(idx_map, key=lambda c: idx_map[c])
selected = monitor.get_selected()

# ----------------------------------------------------------------------
# Keep the multiselect widget in sync with the monitor's selection.
#
# Streamlit garbage-collects a keyed widget's state whenever the widget is
# NOT rendered on a run — which happens every time a sidebar button calls
# st.rerun() (that aborts before this page renders) or you navigate away.
# If we didn't restore it, the multiselect would come back EMPTY and wipe
# the saved selection. So we re-seed it from the monitor (the source of
# truth, persisted in SQLite) whenever its key is missing, and also when
# the selection changed elsewhere (✕ remove, Clear all, watchlist load).
# ----------------------------------------------------------------------
if ("dash_select" not in st.session_state
        or "_dash_sync" not in st.session_state
        or set(st.session_state.get("_dash_sync", [])) != set(selected)):
    st.session_state["dash_select"] = list(selected)
    st.session_state["_dash_sync"] = list(selected)

picked = st.multiselect(
    "Select stocks to monitor",
    options=all_codes,
    format_func=lambda c: f"{idx_map.get(c, '?')}. {c}",
    placeholder="Search by trading code or index number…",
    key="dash_select",
    help="Type to search 396+ stocks by code or index. Add as many as you "
         "like — each becomes a live card below.",
)
# Persist genuine edits. An empty multiselect never auto-wipes a non-empty
# selection (use the explicit '🗑 Clear all' button for that) — this is the
# final guard against a widget that came back empty after Streamlit GC.
if set(picked) != set(selected) and (picked or not selected):
    added = [c for c in picked if c not in selected]
    removed = [c for c in selected if c not in picked]
    monitor.set_selected(picked)
    # One toast per change (cascading), capped so a huge bulk edit can't
    # spawn dozens of toasts.
    changes = ([(c, "added", "➕") for c in added]
               + [(c, "removed", "🗑") for c in removed])
    for code_, verb, icon in changes[:6]:
        flash(f"{code_} {verb}", icon)
    if len(changes) > 6:
        flash(f"+{len(changes) - 6} more changes", "ℹ️")
    st.rerun()

CARDS_PER_ROW = 2

top = st.columns([3, 1, 1])
with top[1]:
    if st.button("🗑 Clear all", width="stretch", disabled=not selected):
        request_confirm("_clear_all")
with top[2]:
    if st.button("⚡ Refresh", width="stretch"):
        monitor.refresh_now()
        flash("Prices refreshed", "⚡")
        st.rerun()

st.markdown(
    f'{pill(f"{len(selected)} STOCKS TRACKED", "violet")}',
    unsafe_allow_html=True,
)

# A ✕ on a card sets this flag (from inside the live fragment); we open the
# confirmation modal here at the top level.
if pending := st.session_state.get("_pending_remove"):
    confirm_action(
        f"Remove {pending} from your dashboard?",
        "The live card is removed. Any price history already collected is kept.",
        on_confirm=lambda c=pending: monitor.remove_selected(c),
        clear_key="_pending_remove",
        confirm_label="🗑 Yes, remove",
        success_message=f"{pending} removed", success_icon="🗑",
    )

if st.session_state.get("_clear_all"):
    confirm_action(
        "Remove all stocks from your dashboard?",
        "This clears every card. Your watchlists and alert rules are kept.",
        on_confirm=lambda: monitor.set_selected([]),
        clear_key="_clear_all",
        confirm_label="🗑 Yes, clear all",
        success_message="Dashboard cleared", success_icon="🗑",
    )

if not selected:
    st.info("👆 No stocks selected yet. Use the search box above (or the "
            "**Market Overview**) to add stocks — they'll appear here as "
            "live cards.")
    st.stop()


def _save_band(code: str, lo: float, hi: float, condition: str = "range") -> None:
    monitor.set_price_bounds(code, lo, hi, condition)
    desc = {
        "above": f"LTP ≥ {lo:g}",
        "below": f"LTP ≤ {hi:g}",
        "range": f"band {min(lo, hi):g}–{max(lo, hi):g}",
        "outside": f"outside {min(lo, hi):g}–{max(lo, hi):g}",
    }.get(condition, f"{lo:g}–{hi:g}")
    flash(f"{code} tracking {desc} BDT", "🎯")


def _clear_band(code: str) -> None:
    monitor.clear_price_bounds(code)
    flash(f"{code} band cleared", "🧹")


@st.fragment(run_every="12s")
def cards_grid() -> None:
    live = [monitor.get_quote(c) for c in monitor.get_selected()]
    live = [q for q in live if q is not None]
    detail_code, remove_code = render_cards(
        live, cols=CARDS_PER_ROW, key_prefix="dash",
        show_remove=True, ai_lookup=monitor.ai_result,
        bounds_lookup=monitor.get_price_bounds,
        hits_lookup=monitor.condition_hits,
        on_save_band=_save_band, on_clear_band=_clear_band,
    )
    if remove_code:
        st.session_state["_pending_remove"] = remove_code
        st.rerun()
    if detail_code:
        st.session_state["detail_code"] = detail_code
        st.switch_page("views/details.py")
    st.caption("Cards auto-refresh every 12 seconds · set a **🎯 price "
               "condition** on any card to track how often it triggers")


cards_grid()
