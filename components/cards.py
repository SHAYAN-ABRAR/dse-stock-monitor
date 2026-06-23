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
from utils import fmt_compact, fmt_money, fmt_signed

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
# Per-condition copy for the live "hit" counter beside the price.
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


def band_button_label(bounds: Optional[dict]) -> str:
    """Compact label for the card's price-condition popover trigger."""
    if not bounds:
        return "Set price condition"
    cond = bounds.get("condition", "range")
    lo, hi = bounds.get("low"), bounds.get("high")
    if cond == "above" and lo is not None:
        return f"LTP ≥ {lo:g} BDT"
    if cond == "below" and hi is not None:
        return f"LTP ≤ {hi:g} BDT"
    if lo is not None and hi is not None:
        return (f"Outside {lo:g}–{hi:g} BDT" if cond == "outside"
                else f"Band {lo:g}–{hi:g} BDT")
    return "Set price condition"


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


def hit_box_html(bounds: Optional[dict], hits: int,
                 satisfied_now: Optional[bool]) -> str:
    """Display-only HTML for the live counter beside the price.

    Adapts its title, chip and sub-line to the tracked condition
    (``above``/``below``/``range``/``outside``).
    """
    if not bounds:
        return (
            '<div class="hit-box hit-unset">'
            '<div class="hit-top"><span class="hit-icon">🎯</span>'
            '<span class="hit-title">Times hit</span></div>'
            '<div class="hit-count">—</div>'
            '<div class="hit-sub">Set a condition below to start counting</div>'
            '</div>'
        )
    cond = bounds.get("condition", "range")
    title, chip_in, chip_out, sub_tpl = _HIT_META.get(cond, _HIT_META["range"])
    lo = bounds.get("low") if bounds.get("low") is not None else 0.0
    hi = bounds.get("high") if bounds.get("high") is not None else 0.0
    if satisfied_now is True:
        state = "hit-in"
        chip = f'<span class="hit-chip chip-in">{chip_in}</span>'
    elif satisfied_now is False:
        state = "hit-out"
        chip = f'<span class="hit-chip chip-out">{chip_out}</span>'
    else:
        state, chip = "hit-out", ""
    sub = sub_tpl.format(lo=lo, hi=hi)
    return f"""
    <div class="hit-box {state}">
      <div class="hit-top">
        <span class="hit-icon">🎯</span>
        <span class="hit-title">{title}</span>
        {chip}
      </div>
      <div class="hit-count">{hits}</div>
      <div class="hit-sub">{sub}</div>
    </div>
    """


def card_body_html(q: StockQuote, ai: Optional[AnalysisResult] = None,
                   hit_html: str = "") -> str:
    """Return the HTML for the top section of a card (header, price, stats).

    This is the content that lives *inside* the card container — the card
    frame itself is a real Streamlit container (so interactive controls can
    sit inside it), styled via the ``st-key-card_`` CSS. ``hit_html`` (the
    'times in band' counter) is placed to the right of the live price.
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
        <div class="sc-priceblock">
          <div class="sc-ltp">{ltp} <small>BDT</small></div>
          <div class="sc-change dir-{direction}">{arrow}&nbsp;{change} &nbsp;·&nbsp; {pct_str}</div>
        </div>
        {hit_html}
      </div>
      <div class="sc-stats">
        <div class="sc-stat"><div class="v">{fmt_compact(q.volume)}</div><div class="k">Volume</div></div>
        <div class="sc-stat"><div class="v">{fmt_compact(q.value_mn)}M</div><div class="k">Value</div></div>
        <div class="sc-stat"><div class="v">{fmt_compact(q.trades)}</div><div class="k">Trades</div></div>
      </div>
      <div class="sc-foot"><span class="live-dot"></span> Updated {updated}{age_part} {('· ' + ai_chip) if ai_chip else ''}</div>
    </div>
    """


def _render_band_setter(
    q: StockQuote, key_prefix: str, *, bounds: Optional[dict] = None,
    on_save_band=None, on_clear_band=None,
) -> None:
    """Render the per-card price-condition setter (Condition + price inputs).

    Supports the same four conditions as the Alerts page; the live counter is
    rendered separately, beside the price.
    """
    code = q.code
    ref = q.ltp if q.ltp is not None else (q.close or q.ycp or 0.0)
    step = _price_step(ref)

    saved_cond = bounds.get("condition", "range") if bounds else "above"
    b_lo = bounds.get("low") if bounds else None
    b_hi = bounds.get("high") if bounds else None

    # Compact dropdown (popover): the card shows just this trigger; the
    # condition panel opens on click, so the card stays small.
    #
    # Streamlit has no API to close a popover programmatically, and a plain
    # st.rerun() leaves it open. Rotating the popover key on save/clear mounts
    # a fresh (closed) popover instead. The inner widgets keep their own stable
    # keys, so the values the user just set still persist.
    nonce_key = f"_bandpop_nonce_{key_prefix}_{code}"
    nonce = st.session_state.get(nonce_key, 0)
    with st.popover(band_button_label(bounds), icon="🎯", width="stretch",
                    key=f"bandpop_{key_prefix}_{code}_{nonce}"):
        st.markdown(
            '<div class="band-head"><span class="band-ico">🎯</span>'
            '<span>Track a price condition</span></div>',
            unsafe_allow_html=True)

        # A radio (not selectbox) so the choice is mouse-click only — a
        # Streamlit selectbox is a searchable combobox you can type into.
        condition = st.radio(
            "Condition", options=COND_OPTIONS,
            index=COND_OPTIONS.index(saved_cond),
            format_func=lambda c: COND_LABELS[c],
            key=f"{key_prefix}_bcond_{code}",
        )

        # Adaptive inputs: one threshold for above/below, a band otherwise.
        if condition == "above":
            val = st.number_input(
                "Trigger when LTP ≥ (BDT)", min_value=0.0,
                value=float(b_lo if b_lo is not None else (ref or 1)),
                step=step, format="%.2f", key=f"{key_prefix}_bv_{code}")
            save_lo, save_hi = val, val
            st.caption("Counts each time LTP **rises to / above** your target.")
        elif condition == "below":
            val = st.number_input(
                "Trigger when LTP ≤ (BDT)", min_value=0.0,
                value=float(b_hi if b_hi is not None else (ref or 1)),
                step=step, format="%.2f", key=f"{key_prefix}_bv_{code}")
            save_lo, save_hi = val, val
            st.caption("Counts each time LTP **falls to / below** your target.")
        else:
            ci = st.columns(2, gap="small")
            save_lo = ci[0].number_input(
                "Low (BDT)", min_value=0.0,
                value=float(b_lo if b_lo is not None else (ref or 1) * 0.95),
                step=step, format="%.2f", key=f"{key_prefix}_blo_{code}")
            save_hi = ci[1].number_input(
                "High (BDT)", min_value=0.0,
                value=float(b_hi if b_hi is not None else (ref or 1) * 1.05),
                step=step, format="%.2f", key=f"{key_prefix}_bhi_{code}")
            st.caption(
                "Counts each time LTP **enters** your band." if condition == "range"
                else "Counts each time LTP **exits** your band.")

        cb = st.columns([3, 1], gap="small")
        if cb[0].button("💾 Save", type="primary", width="stretch",
                        key=f"{key_prefix}_bsave_{code}"):
            if on_save_band:
                on_save_band(code, save_lo, save_hi, condition)
            st.session_state[nonce_key] = nonce + 1  # re-mount popover closed
            st.rerun()
        if cb[1].button("✕", width="stretch", disabled=not bounds,
                        help="Clear this condition",
                        key=f"{key_prefix}_bclr_{code}"):
            if on_clear_band:
                on_clear_band(code)
            st.session_state[nonce_key] = nonce + 1  # re-mount popover closed
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
) -> Tuple[Optional[str], Optional[str]]:
    """
    Render a responsive grid of stock cards.

    Returns ``(detail_code, remove_code)`` — the trading code the user asked
    to view details for, and the one they asked to remove (each or both may
    be None). The caller decides what to do (e.g. confirm before removing).
    ``ai_lookup`` is an optional callable code -> AnalysisResult.

    When ``bounds_lookup``/``hits_lookup``/``on_save_band``/``on_clear_band``
    are supplied, each card also shows the LTP-band setter and the
    "times in band" hit counter.
    """
    detail_code: Optional[str] = None
    remove_code: Optional[str] = None
    show_band = bounds_lookup is not None
    for start in range(0, len(quotes), cols):
        row = quotes[start:start + cols]
        columns = st.columns(cols, gap="large")
        for col, q in zip(columns, row):
            with col:
                ai = ai_lookup(q.code) if ai_lookup else None
                # Counter beside the price: compute bounds/hits once and embed
                # the 'times in band' box to the right of the LTP.
                bounds = bounds_lookup(q.code) if (show_band and bounds_lookup) else None
                hit_html = ""
                if show_band:
                    hits = 0
                    satisfied_now: Optional[bool] = None
                    if bounds:
                        cond = bounds.get("condition", "range")
                        lo, hi = bounds.get("low"), bounds.get("high")
                        if hits_lookup:
                            hits = hits_lookup(q.code, cond, lo, hi)
                        satisfied_now = condition_satisfied(cond, q.ltp, lo, hi)
                    hit_html = hit_box_html(bounds, hits, satisfied_now)
                # The whole card is one real Streamlit container so the band
                # setter (live widgets) sits INSIDE the card. Direction is
                # encoded in the key to colour the accent rail.
                with st.container(border=True,
                                  key=f"card_{q.direction}_{key_prefix}_{q.code}"):
                    st.markdown(card_body_html(q, ai, hit_html),
                                unsafe_allow_html=True)
                    if show_remove:
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
                        if st.button("View Details",
                                     key=f"{key_prefix}_d_{q.code}",
                                     width="stretch"):
                            detail_code = q.code
                    if show_band:
                        _render_band_setter(
                            q, key_prefix, bounds=bounds,
                            on_save_band=on_save_band, on_clear_band=on_clear_band,
                        )
                # breathing room so the next row doesn't collide
                st.markdown('<div class="card-spacer"></div>',
                            unsafe_allow_html=True)
    return detail_code, remove_code
