"""
components/cards.py
-------------------
Premium stock-card rendering for the dashboard grid.

Each card is glassmorphic, colour-coded by direction (green up / red down
/ blue flat), and carries an interactive "View Details" + remove control
rendered as real Streamlit buttons beneath the HTML body.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import streamlit as st

from ai_analyzer import AnalysisResult
from market import StockQuote
from utils import fmt_money, fmt_signed

_ARROW = {"up": "▲", "down": "▼", "flat": "◆"}


def relative_age(captured_at: Optional[datetime]) -> str:
    """Human 'time since' for a quote's capture time, e.g. 'just now' / '5m ago'.

    Computed against *now* in the same timezone as ``captured_at`` (the scrape
    stamps are Asia/Dhaka-aware). Because the card re-renders every few seconds,
    this keeps ticking even between scrapes — so a quiet, market-closed gap
    reads as a growing 'Xm ago' instead of a frozen timestamp.
    """
    if not isinstance(captured_at, datetime):
        return ""
    try:
        ref = datetime.now(captured_at.tzinfo)
        secs = (ref - captured_at).total_seconds()
    except Exception:
        return ""
    secs = max(0.0, secs)
    if secs < 10:
        return "just now"
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86_400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86_400)}d ago"

# The four price conditions a card can track (mirrors the Alerts page).
COND_OPTIONS = ["above", "below", "range", "outside"]
COND_LABELS = {
    "above": "LTP rises to / above",
    "below": "LTP falls to / below",
    "range": "LTP enters a band",
    "outside": "LTP exits a band",
}
# Per-condition copy for the live "hit" counter under the price.
# title · chip when satisfied · chip when not · sub-line ({lo}/{hi} filled in).
_HIT_META = {
    "above":   ("Times hit", "● At / above", "○ Below",
                "rose to / above <b>{lo:g}</b> BDT"),
    "below":   ("Times hit", "● At / below", "○ Above",
                "fell to / below <b>{hi:g}</b> BDT"),
    "range":   ("Times in band", "● In band now", "○ Outside",
                "entered your <b>{lo:g} – {hi:g}</b> BDT band"),
    "outside": ("Times out", "● Outside now", "○ Inside",
                "left your <b>{lo:g} – {hi:g}</b> BDT band"),
}


def condition_satisfied(condition: str, ltp: Optional[float],
                        low: Optional[float], high: Optional[float]) -> Optional[bool]:
    """Is the LTP currently satisfying the condition? None when unknown."""
    if ltp is None:
        return None
    if condition == "above":
        return low is not None and ltp >= low
    if condition == "below":
        return high is not None and ltp <= high
    if condition == "outside":
        return (low is not None and high is not None
                and (ltp < low or ltp > high))
    return low is not None and high is not None and low <= ltp <= high


def condition_label(entry: dict) -> str:
    """Compact human label for one tracked condition, e.g. 'LTP ≥ 3.1 BDT'."""
    cond = entry.get("condition", "range")
    lo, hi = entry.get("low"), entry.get("high")
    if cond == "above" and lo is not None:
        return f"LTP ≥ {lo:g} BDT"
    if cond == "below" and hi is not None:
        return f"LTP ≤ {hi:g} BDT"
    if lo is not None and hi is not None:
        return (f"Outside {lo:g}–{hi:g} BDT" if cond == "outside"
                else f"Band {lo:g}–{hi:g} BDT")
    return "Set price condition"


def band_button_label(conditions: Optional[list]) -> str:
    """Compact label for the card's price-condition popover trigger."""
    conds = [e for e in (conditions or []) if isinstance(e, dict)]
    if not conds:
        return "Set price condition"
    if len(conds) == 1:
        return condition_label(conds[0])
    return f"{len(conds)} conditions active"


def _price_step(ref: Optional[float]) -> float:
    """A sensible nudge step for a number input given the price scale."""
    if not ref or ref <= 0:
        return 0.10
    if ref < 10:
        return 0.10
    if ref < 100:
        return 0.50
    if ref < 1000:
        return 1.0
    return 5.0


def hit_box_html(conditions: Optional[list],
                 per_condition: Optional[list] = None) -> str:
    """Display-only HTML for the live counter strip under the price.

    ``conditions`` is the stock's tracked condition list; ``per_condition``
    aligns with it as ``(hits, satisfied_now)`` pairs. Rendered as a title
    row plus ONE single-line row per condition (count · description · state
    chip), so nothing ever wraps and the strip only grows when the user
    tracks more conditions.
    """
    if not conditions:
        return (
            '<div class="hit-box hit-unset">'
            '<div class="hit-top"><span class="hit-icon">🎯</span>'
            '<span class="hit-title">Times hit</span></div>'
            '<div class="hit-row"><span class="hit-count">—</span>'
            '<span class="hit-sub">Set a condition below to start counting</span></div>'
            '</div>'
        )
    per_condition = per_condition or [(0, None)] * len(conditions)
    any_sat = False
    rows = ""
    for entry, (hits, sat) in zip(conditions, per_condition):
        cond = entry.get("condition", "range")
        _, chip_in, chip_out, sub_tpl = _HIT_META.get(cond, _HIT_META["range"])
        lo = entry.get("low") if entry.get("low") is not None else 0.0
        hi = entry.get("high") if entry.get("high") is not None else 0.0
        if sat is True:
            any_sat = True
            chip = f'<span class="hit-chip chip-in">{chip_in}</span>'
        elif sat is False:
            chip = f'<span class="hit-chip chip-out">{chip_out}</span>'
        else:
            chip = ""
        rows += (
            f'<div class="hit-row{" row-in" if sat is True else ""}">'
            f'<span class="hit-count">{hits}</span>'
            f'<span class="hit-sub">{sub_tpl.format(lo=lo, hi=hi)}</span>'
            f'{chip}</div>'
        )
    title = (_HIT_META.get(conditions[0].get("condition", "range"),
                           _HIT_META["range"])[0]
             if len(conditions) == 1 else "Times hit")
    state = "hit-in" if any_sat else "hit-out"
    return f"""
    <div class="hit-box {state}">
      <div class="hit-top">
        <span class="hit-icon">🎯</span>
        <span class="hit-title">{title}</span>
      </div>
      {rows}
    </div>
    """


def card_body_html(q: StockQuote, ai: Optional[AnalysisResult] = None,
                   hit_html: str = "") -> str:
    """Return the HTML for the top section of a card (header, price, counter).

    This is the content that lives *inside* the card container — the card
    frame itself is a real Streamlit container (so interactive controls can
    sit inside it), styled via the ``st-key-card_`` CSS. ``hit_html`` (the
    'times in band' counter) is a full-width strip beneath the live price.
    """
    direction = q.direction
    arrow = _ARROW[direction]
    change = fmt_signed(q.change)
    pct = q.change_pct
    pct_str = f"{pct:+.2f}%" if pct is not None else "—"
    ltp = fmt_money(q.ltp) if q.ltp is not None else "—"
    updated = q.captured_at.strftime("%I:%M:%S %p").lstrip("0")
    age = relative_age(q.captured_at)
    age_part = f" · {age}" if age else ""

    ai_chip = ""
    if ai is not None and ai.is_anomaly:
        ai_chip = '<span style="color:#fbbf24;font-weight:700;">⚡ AI anomaly</span>'

    return f"""
    <div class="sc-body">
      <div class="sc-top">
        <div>
          <div class="sc-code">{q.code}</div>
          <div class="sc-sector">{q.sector}</div>
        </div>
        <span class="sc-idx">#{q.index}</span>
      </div>
      <div class="sc-pricerow">
        <div class="sc-ltp">{ltp} <small>BDT</small></div>
        <div class="sc-change dir-{direction}">{arrow} {change} · {pct_str}</div>
      </div>
      {hit_html}
      <div class="sc-foot"><span class="live-dot"></span> Updated {updated}{age_part} {('· ' + ai_chip) if ai_chip else ''}</div>
    </div>
    """


def _render_band_setter(
    q: StockQuote, key_prefix: str, *, conditions: Optional[list] = None,
    on_save_band=None, on_clear_band=None,
) -> None:
    """Render the per-card price-condition setter (checkboxes + inputs).

    Supports the same four conditions as the Alerts page, and SEVERAL can be
    tracked at once: each ticked checkbox reveals that condition's own
    threshold / band inputs. Save persists exactly the ticked set; the live
    counters are rendered separately, under the price.
    """
    code = q.code
    ref = q.ltp if q.ltp is not None else (q.close or q.ycp or 0.0)
    step = _price_step(ref)
    saved = {e.get("condition", "range"): e
             for e in (conditions or []) if isinstance(e, dict)}

    # Compact dropdown (popover): the card shows just this trigger; the
    # condition panel opens on click, so the card stays small.
    #
    # Streamlit has no API to close a popover programmatically, and a plain
    # st.rerun() leaves it open. Rotating the popover key on save/clear mounts
    # a fresh (closed) popover instead. The inner widgets keep their own stable
    # keys, so the values the user just set still persist.
    nonce_key = f"_bandpop_nonce_{key_prefix}_{code}"
    nonce = st.session_state.get(nonce_key, 0)
    with st.popover(band_button_label(conditions), icon="🎯", width="stretch",
                    key=f"bandpop_{key_prefix}_{code}_{nonce}"):
        st.markdown(
            '<div class="band-head"><span class="band-ico">🎯</span>'
            '<span>Track price conditions</span></div>',
            unsafe_allow_html=True)
        st.caption("Tick every condition to track — each one counts hits "
                   "and chimes on its own.")

        # One checkbox per condition; a ticked one reveals its own inputs,
        # so several conditions can be armed side by side.
        entries: list = []
        for cond in COND_OPTIONS:
            ticked = st.checkbox(
                COND_LABELS[cond], value=cond in saved,
                key=f"{key_prefix}_bc_{cond}_{code}")
            if not ticked:
                continue
            e = saved.get(cond) or {}
            if cond == "above":
                val = st.number_input(
                    "Trigger when LTP ≥ (BDT)", min_value=0.0,
                    value=float(e["low"] if e.get("low") is not None
                                else (ref or 1)),
                    step=step, format="%.2f",
                    key=f"{key_prefix}_bv_above_{code}")
                entries.append(("above", val, val))
            elif cond == "below":
                val = st.number_input(
                    "Trigger when LTP ≤ (BDT)", min_value=0.0,
                    value=float(e["high"] if e.get("high") is not None
                                else (ref or 1)),
                    step=step, format="%.2f",
                    key=f"{key_prefix}_bv_below_{code}")
                entries.append(("below", val, val))
            else:
                ci = st.columns(2, gap="small")
                lo = ci[0].number_input(
                    "Low (BDT)", min_value=0.0,
                    value=float(e["low"] if e.get("low") is not None
                                else (ref or 1) * 0.95),
                    step=step, format="%.2f",
                    key=f"{key_prefix}_blo_{cond}_{code}")
                hi = ci[1].number_input(
                    "High (BDT)", min_value=0.0,
                    value=float(e["high"] if e.get("high") is not None
                                else (ref or 1) * 1.05),
                    step=step, format="%.2f",
                    key=f"{key_prefix}_bhi_{cond}_{code}")
                entries.append((cond, lo, hi))

        cb = st.columns([3, 1], gap="small")
        if cb[0].button("💾 Save", type="primary", width="stretch",
                        key=f"{key_prefix}_bsave_{code}"):
            if on_save_band:
                on_save_band(code, entries)
            st.session_state[nonce_key] = nonce + 1  # re-mount popover closed
            st.rerun()
        if cb[1].button("✕", width="stretch", disabled=not saved,
                        help="Clear every condition on this stock",
                        key=f"{key_prefix}_bclr_{code}"):
            if on_clear_band:
                on_clear_band(code)
            # Drop the checkbox states so they re-seed unticked next run
            # (their keys survive the popover re-mount otherwise).
            for cond in COND_OPTIONS:
                st.session_state.pop(f"{key_prefix}_bc_{cond}_{code}", None)
            st.session_state[nonce_key] = nonce + 1  # re-mount popover closed
            st.rerun()


def _render_bell(col, code: str, key_prefix: str,
                 bell_muted_lookup, on_toggle_bell) -> None:
    """YouTube-style notification bell: armed / muted, per stock.

    The label is a Material icon (not an emoji): colour-emoji glyphs render
    taller than their line box and get clipped inside compact buttons,
    while the icon font sizes exactly.
    """
    muted = bool(bell_muted_lookup(code)) if bell_muted_lookup else False
    state = "off" if muted else "on"
    tip = (f"Notifications for {code} are MUTED — click to re-arm the chime "
           "and tab alert" if muted else
           f"Notifications for {code} are ON — a price-condition hit chimes "
           "and flashes this tab. Click to mute")
    icon = (":material/notifications_off:" if muted
            else ":material/notifications_active:")
    if col.button(icon, width="stretch",
                  key=f"{key_prefix}_bell_{state}_{code}", help=tip):
        if on_toggle_bell:
            on_toggle_bell(code, not muted)
        st.rerun()


def render_cards(
    quotes: List[StockQuote],
    *,
    cols: int = 3,
    key_prefix: str = "card",
    show_remove: bool = True,
    ai_lookup=None,
    bounds_lookup=None,
    hits_lookup=None,
    on_save_band=None,
    on_clear_band=None,
    bell_muted_lookup=None,
    on_toggle_bell=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Render a responsive grid of stock cards.

    Returns ``(detail_code, remove_code)`` — the trading code the user asked
    to view details for, and the one they asked to remove (each or both may
    be None). The caller decides what to do (e.g. confirm before removing).
    ``ai_lookup`` is an optional callable code -> AnalysisResult.

    When ``bounds_lookup``/``hits_lookup``/``on_save_band``/``on_clear_band``
    are supplied, each card also shows the condition setter and one live hit
    counter per tracked condition. ``bounds_lookup`` returns a stock's full
    condition list (``monitor.get_price_conditions``). With
    ``bell_muted_lookup``/``on_toggle_bell``, each card gets a 🔔 bell that
    arms / mutes that stock's hit notifications (chime + tab flash).
    """
    detail_code: Optional[str] = None
    remove_code: Optional[str] = None
    show_band = bounds_lookup is not None
    for start in range(0, len(quotes), cols):
        row = quotes[start:start + cols]
        columns = st.columns(cols, gap="medium")
        for col, q in zip(columns, row):
            with col:
                ai = ai_lookup(q.code) if ai_lookup else None
                # Counters under the price: compute hits/satisfied once per
                # tracked condition and embed the strip beneath the LTP.
                conditions = (bounds_lookup(q.code) or []) if show_band else []
                hit_html = ""
                if show_band:
                    per = []
                    for e in conditions:
                        cond = e.get("condition", "range")
                        lo, hi = e.get("low"), e.get("high")
                        hits = (hits_lookup(q.code, cond, lo, hi)
                                if hits_lookup else 0)
                        per.append((hits,
                                    condition_satisfied(cond, q.ltp, lo, hi)))
                    hit_html = hit_box_html(conditions, per)
                # The whole card is one real Streamlit container so the band
                # setter (live widgets) sits INSIDE the card. Direction is
                # encoded in the key to colour the accent rail.
                with st.container(border=True,
                                  key=f"card_{q.direction}_{key_prefix}_{q.code}"):
                    st.markdown(card_body_html(q, ai, hit_html),
                                unsafe_allow_html=True)
                    has_bell = on_toggle_bell is not None
                    if show_remove:
                        if has_bell:
                            b1, bb, b2 = st.columns([2.6, 0.7, 0.7])
                            _render_bell(bb, q.code, key_prefix,
                                         bell_muted_lookup, on_toggle_bell)
                        else:
                            b1, b2 = st.columns([3, 1])
                        if b1.button("View Details",
                                     key=f"{key_prefix}_d_{q.code}",
                                     width="stretch"):
                            detail_code = q.code
                        if b2.button("✕", key=f"{key_prefix}_x_{q.code}",
                                     help=f"Remove {q.code} from dashboard",
                                     width="stretch"):
                            remove_code = q.code
                    else:
                        if has_bell:
                            b1, bb = st.columns([3.3, 0.7])
                            _render_bell(bb, q.code, key_prefix,
                                         bell_muted_lookup, on_toggle_bell)
                        else:
                            b1 = st
                        if b1.button("View Details",
                                     key=f"{key_prefix}_d_{q.code}",
                                     width="stretch"):
                            detail_code = q.code
                    if show_band:
                        _render_band_setter(
                            q, key_prefix, conditions=conditions,
                            on_save_band=on_save_band, on_clear_band=on_clear_band,
                        )
                # breathing room so the next row doesn't collide
                st.markdown('<div class="card-spacer"></div>',
                            unsafe_allow_html=True)
    return detail_code, remove_code
