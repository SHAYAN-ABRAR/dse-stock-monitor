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

from components.cards import card_display_name, render_cards
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

CARDS_PER_ROW = 4

top = st.columns([3, 1, 1])
with top[1]:
    if st.button("🗑 Clear all", width="stretch", disabled=not selected):
        request_confirm("_clear_all")
with top[2]:
    if st.button("⚡ Refresh", width="stretch"):
        monitor.refresh_now()
        flash("Prices refreshed", "⚡")
        st.rerun()

_copies_map = monitor.get_card_copies()
_n_cards = len(selected) + sum(len(_copies_map.get(c, [])) for c in selected)
st.markdown(
    pill(f"{len(selected)} STOCKS · {_n_cards} CARDS" if _n_cards != len(selected)
         else f"{len(selected)} STOCKS TRACKED", "violet"),
    unsafe_allow_html=True,
)

# A ✕ on a card sets this flag (from inside the live fragment); we open the
# confirmation modal here at the top level.
if pending := st.session_state.get("_pending_remove"):
    confirm_action(
        f"Remove {pending} from your dashboard?",
        "The live card and its duplicate cards are removed. Any price "
        "history already collected is kept.",
        on_confirm=lambda c=pending: monitor.remove_dashboard_stock(c),
        clear_key="_pending_remove",
        confirm_label="🗑 Yes, remove",
        success_message=f"{pending} removed", success_icon="🗑",
    )

if st.session_state.get("_clear_all"):
    confirm_action(
        "Remove all stocks from your dashboard?",
        "This clears every card (duplicates included). Your watchlists and "
        "alert rules are kept.",
        on_confirm=lambda: [monitor.remove_dashboard_stock(c)
                            for c in monitor.get_selected()],
        clear_key="_clear_all",
        confirm_label="🗑 Yes, clear all",
        success_message="Dashboard cleared", success_icon="🗑",
    )

if not selected:
    st.info("👆 No stocks selected yet. Use the search box above (or the "
            "**Market Overview**) to add stocks — they'll appear here as "
            "live cards.")
    st.stop()


def _save_band(slot: str, entries: list) -> None:
    """Persist the popover's full set of ticked conditions for one card."""
    monitor.set_price_conditions(slot, entries)
    name = card_display_name(slot)
    if not entries:
        flash(f"{name} conditions cleared", "🧹")
        return
    parts = []
    for condition, lo, hi in entries:
        parts.append({
            "above": f"LTP ≥ {lo:g}",
            "below": f"LTP ≤ {hi:g}",
            "range": f"band {min(lo, hi):g}–{max(lo, hi):g}",
            "outside": f"outside {min(lo, hi):g}–{max(lo, hi):g}",
        }.get(condition, f"{lo:g}–{hi:g}"))
    flash(f"{name} tracking {' · '.join(parts)} BDT", "🎯")


def _clear_band(slot: str) -> None:
    monitor.clear_price_bounds(slot)
    flash(f"{card_display_name(slot)} conditions cleared", "🧹")


def _toggle_bell(slot: str, muted: bool) -> None:
    monitor.set_bell_muted(slot, muted)
    flash(f"{card_display_name(slot)} notifications {'muted' if muted else 'on'}",
          "🔕" if muted else "🔔")


def _duplicate_card(slot: str) -> None:
    """Clone a card into a new independent duplicate of the same stock."""
    new_slot = monitor.add_card_copy(slot)
    flash(f"{card_display_name(new_slot)} created — its conditions are "
          "independent of the original card", "➕")


@st.fragment(run_every="12s")
def cards_grid() -> None:
    # One card per selected stock, plus that stock's duplicate cards right
    # after it — each duplicate is an independent (quote, slot) instance.
    copies = monitor.get_card_copies()
    live = []
    for c in monitor.get_selected():
        q = monitor.get_quote(c)
        if q is None:
            continue
        live.append((q, c))
        for n in copies.get(c, []):
            live.append((q, f"{c}#{n}"))
    detail_code, remove_slot = render_cards(
        live, cols=CARDS_PER_ROW, key_prefix="dash",
        show_remove=True, ai_lookup=monitor.ai_result,
        bounds_lookup=monitor.get_price_conditions,
        hits_lookup=monitor.condition_hits,
        on_save_band=_save_band, on_clear_band=_clear_band,
        bell_muted_lookup=monitor.is_bell_muted, on_toggle_bell=_toggle_bell,
        on_duplicate=_duplicate_card,
    )
    if remove_slot:
        if "#" in remove_slot:
            # Duplicates are disposable observation cards — drop instantly.
            monitor.remove_card_copy(remove_slot)
            flash(f"{card_display_name(remove_slot)} removed", "🗑")
        else:
            st.session_state["_pending_remove"] = remove_slot
        st.rerun()
    if detail_code:
        st.session_state["detail_code"] = detail_code
        st.switch_page("views/details.py")
    st.caption("Cards auto-refresh every 12 seconds · set a **🎯 price "
               "condition** on any card · **＋** duplicates a card so the "
               "same stock can be observed with different parameters")


cards_grid()
