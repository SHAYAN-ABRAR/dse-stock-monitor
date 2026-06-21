"""
components/cards.py
-------------------
Premium stock-card rendering for the dashboard grid.

Each card is glassmorphic, colour-coded by direction (green up / red down
/ blue flat), and carries an interactive "View Details" + remove control
rendered as real Streamlit buttons beneath the HTML body.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import streamlit as st

from ai_analyzer import AnalysisResult
from market import StockQuote
from utils import fmt_compact, fmt_money, fmt_signed

_ARROW = {"up": "▲", "down": "▼", "flat": "◆"}


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
                 in_band_now: Optional[bool]) -> str:
    """Display-only HTML for the 'times in band' counter beside the price."""
    if not bounds:
        return (
            '<div class="hit-box hit-unset">'
            '<div class="hit-top"><span class="hit-icon">🎯</span>'
            '<span class="hit-title">Times in band</span></div>'
            '<div class="hit-count">—</div>'
            '<div class="hit-sub">Set a band below to start counting</div>'
            '</div>'
        )
    lo, hi = bounds["low"], bounds["high"]
    if in_band_now is True:
        state = "hit-in"
        chip = '<span class="hit-chip chip-in">● In band now</span>'
    elif in_band_now is False:
        state = "hit-out"
        chip = '<span class="hit-chip chip-out">○ Outside</span>'
    else:
        state, chip = "hit-out", ""
    return f"""
    <div class="hit-box {state}">
      <div class="hit-top">
        <span class="hit-icon">🎯</span>
        <span class="hit-title">Times in band</span>
        {chip}
      </div>
      <div class="hit-count">{hits}</div>
      <div class="hit-sub">entered your <b>{lo:g} – {hi:g}</b> BDT band</div>
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
      <div class="sc-foot"><span class="live-dot"></span> Updated {updated} {('· ' + ai_chip) if ai_chip else ''}</div>
    </div>
    """


def _render_band_setter(
    q: StockQuote, key_prefix: str, *, bounds: Optional[dict] = None,
    on_save_band=None, on_clear_band=None,
) -> None:
    """Render the per-card LTP band setter (Low → High inputs + Save/Clear).

    The 'times in band' counter is rendered separately, beside the price.
    """
    code = q.code
    ref = q.ltp if q.ltp is not None else (q.close or q.ycp or 0.0)
    step = _price_step(ref)
    def_lo = round(bounds["low"] if bounds else (ref or 1) * 0.95, 2)
    def_hi = round(bounds["high"] if bounds else (ref or 1) * 1.05, 2)

    # Compact dropdown (popover): the card shows just this trigger; the
    # Low/High panel opens on click, so the card stays small.
    label = (f"LTP band: {bounds['low']:g} – {bounds['high']:g} BDT"
             if bounds else "Set LTP band")
    with st.popover(label, icon="🎯", width="stretch",
                    key=f"bandpop_{key_prefix}_{code}"):
        st.markdown(
            '<div class="band-head"><span class="band-ico">🎯</span>'
            '<span>Set your LTP band</span></div>',
            unsafe_allow_html=True)
        ci = st.columns(2, gap="small")
        lo = ci[0].number_input(
            "Low (BDT)", min_value=0.0, value=float(def_lo), step=step,
            format="%.2f", key=f"{key_prefix}_blo_{code}")
        hi = ci[1].number_input(
            "High (BDT)", min_value=0.0, value=float(def_hi), step=step,
            format="%.2f", key=f"{key_prefix}_bhi_{code}")
        cb = st.columns([3, 1], gap="small")
        if cb[0].button("💾 Save band", type="primary", width="stretch",
                        key=f"{key_prefix}_bsave_{code}"):
            if on_save_band:
                on_save_band(code, lo, hi)
            st.rerun()
        if cb[1].button("✕", width="stretch", disabled=not bounds,
                        help="Clear this band",
                        key=f"{key_prefix}_bclr_{code}"):
            if on_clear_band:
                on_clear_band(code)
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
                    in_band_now: Optional[bool] = None
                    if bounds:
                        if hits_lookup:
                            hits = hits_lookup(q.code, bounds["low"], bounds["high"])
                        if q.ltp is not None:
                            in_band_now = bounds["low"] <= q.ltp <= bounds["high"]
                    hit_html = hit_box_html(bounds, hits, in_band_now)
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
