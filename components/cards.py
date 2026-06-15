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


def card_html(q: StockQuote, ai: Optional[AnalysisResult] = None) -> str:
    """Return the HTML body for one stock card."""
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
    <div class="stock-card sc-{direction}">
      <div class="sc-top">
        <div>
          <div class="sc-code">{q.code}</div>
          <div class="sc-sector">{q.sector}</div>
        </div>
        <span class="sc-idx">#{q.index}</span>
      </div>
      <div class="sc-ltp">{ltp} <small>BDT</small></div>
      <div class="sc-change">{arrow}&nbsp;{change} &nbsp;·&nbsp; {pct_str}</div>
      <div class="sc-stats">
        <div class="sc-stat"><div class="v">{fmt_compact(q.volume)}</div><div class="k">Volume</div></div>
        <div class="sc-stat"><div class="v">{fmt_compact(q.value_mn)}M</div><div class="k">Value</div></div>
        <div class="sc-stat"><div class="v">{fmt_compact(q.trades)}</div><div class="k">Trades</div></div>
      </div>
      <div class="sc-foot"><span class="live-dot"></span> Updated {updated} {('· ' + ai_chip) if ai_chip else ''}</div>
    </div>
    """


def render_cards(
    quotes: List[StockQuote],
    *,
    cols: int = 3,
    key_prefix: str = "card",
    show_remove: bool = True,
    ai_lookup=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Render a responsive grid of stock cards.

    Returns ``(detail_code, remove_code)`` — the trading code the user asked
    to view details for, and the one they asked to remove (each or both may
    be None). The caller decides what to do (e.g. confirm before removing).
    ``ai_lookup`` is an optional callable code -> AnalysisResult.
    """
    detail_code: Optional[str] = None
    remove_code: Optional[str] = None
    for start in range(0, len(quotes), cols):
        row = quotes[start:start + cols]
        columns = st.columns(cols, gap="medium")
        for col, q in zip(columns, row):
            with col:
                ai = ai_lookup(q.code) if ai_lookup else None
                st.markdown(card_html(q, ai), unsafe_allow_html=True)
                if show_remove:
                    b1, b2 = st.columns([3, 1])
                    if b1.button("View Details", key=f"{key_prefix}_d_{q.code}",
                                 width="stretch"):
                        detail_code = q.code
                    if b2.button("✕", key=f"{key_prefix}_x_{q.code}",
                                 help=f"Remove {q.code} from dashboard",
                                 width="stretch"):
                        remove_code = q.code
                else:
                    if st.button("View Details", key=f"{key_prefix}_d_{q.code}",
                                 width="stretch"):
                        detail_code = q.code
                # breathing room so the next row doesn't collide with buttons
                st.markdown('<div class="card-spacer"></div>',
                            unsafe_allow_html=True)
    return detail_code, remove_code
