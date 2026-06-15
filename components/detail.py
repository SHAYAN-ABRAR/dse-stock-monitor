"""
components/detail.py
--------------------
The detailed stock analytics view: basic info, price data, trading
activity, a market-summary panel (day-range + performance gauge +
AI momentum) and the professional Plotly charts.
"""

from __future__ import annotations

import streamlit as st

from components import charts
from market import StockQuote
from utils import fmt_compact, fmt_money, fmt_signed


def _cells(pairs) -> str:
    body = "".join(
        f'<div class="detail-cell"><div class="k">{k}</div>'
        f'<div class="v">{v}</div></div>'
        for k, v in pairs
    )
    return f'<div class="detail-grid">{body}</div>'


def render_stock_detail(monitor, code: str) -> None:
    """Render the full analytics view for one trading code."""
    q: StockQuote | None = monitor.get_quote(code)
    if q is None:
        st.warning(f"No live data for **{code}** yet. Try **Refresh now** "
                   "in the sidebar.")
        return

    direction = q.direction
    pct = q.change_pct
    pct_str = f"{pct:+.2f}%" if pct is not None else "—"
    arrow = {"up": "▲", "down": "▼", "flat": "◆"}[direction]
    color = {"up": "#34d399", "down": "#f87171", "flat": "#60a5fa"}[direction]

    # ---- Header ----
    st.markdown(
        f"""
        <div class="hero" style="margin-bottom:1rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
            <div>
              <h1 style="font-size:1.9rem;">{q.code}
                <span style="font-size:0.9rem;color:#a6bbe0;font-weight:600;">#{q.index} · {q.sector}</span>
              </h1>
              <p style="margin-top:6px;">Dhaka Stock Exchange · live analytics</p>
            </div>
            <div style="text-align:right;">
              <div style="font-size:2.4rem;font-weight:800;color:#fff;line-height:1;">
                {fmt_money(q.ltp)} <span style="font-size:1rem;color:#93a9d4;">BDT</span></div>
              <div style="font-size:1.05rem;font-weight:700;color:{color};margin-top:4px;">
                {arrow} {fmt_signed(q.change)} · {pct_str}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history = monitor.repo.get_history(code, limit=500)
    ai = monitor.ai_result(code)

    # ---- Info / Price / Activity ----
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="section-title">🏷️ Basic Information</div>',
                    unsafe_allow_html=True)
        st.markdown(_cells([
            ("Index No.", f"#{q.index}"),
            ("Trading Code", q.code),
            ("Company", q.display_name),
            ("Sector", q.sector),
        ]), unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="section-title">💵 Price Data</div>',
                    unsafe_allow_html=True)
        st.markdown(_cells([
            ("LTP", fmt_money(q.ltp)),
            ("Day High", fmt_money(q.high)),
            ("Day Low", fmt_money(q.low)),
            ("Prev Close (YCP)", fmt_money(q.ycp)),
            ("Close", fmt_money(q.close)),
            ("Change %", pct_str),
        ]), unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="section-title">📊 Trading Activity</div>',
                    unsafe_allow_html=True)
        st.markdown(_cells([
            ("Volume", fmt_compact(q.volume)),
            ("Value (mn)", fmt_money(q.value_mn)),
            ("Total Trades", fmt_compact(q.trades)),
            ("Change", fmt_signed(q.change)),
        ]), unsafe_allow_html=True)

    # ---- Market summary: day range + gauge + momentum ----
    st.markdown('<div class="section-title">🧭 Market Summary</div>',
                unsafe_allow_html=True)
    s1, s2 = st.columns([1.4, 1])
    with s1:
        st.caption("Day range — where the LTP sits between today's low and high")
        st.plotly_chart(charts.day_range_bar(q.low, q.high, q.ltp),
                        width="stretch", key=f"range_{code}")
        momentum = "Neutral"
        if ai is not None:
            momentum = ai.note
        badge = "blue"
        if direction == "up":
            badge = "green"
        elif direction == "down":
            badge = "red"
        st.markdown(
            f'<span class="pill pill-{badge}">Momentum · {momentum}</span>',
            unsafe_allow_html=True)
    with s2:
        st.plotly_chart(charts.performance_gauge(pct),
                        width="stretch", key=f"gauge_{code}")

    # ---- Charts ----
    st.markdown('<div class="section-title">📈 Live Price Trend</div>',
                unsafe_allow_html=True)
    pts = monitor.repo.history_points(code)
    if pts == 0:
        st.info("History builds automatically while monitoring runs and this "
                "stock is tracked (selected, watchlisted, or has an alert). "
                "Charts populate within a few refresh cycles.")
    st.plotly_chart(charts.price_trend(history, q.ycp),
                    width="stretch", key=f"trend_{code}")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown('<div class="section-title">🔊 Volume Trend</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(charts.volume_trend(history),
                        width="stretch", key=f"vol_{code}")
    with g2:
        st.markdown('<div class="section-title">⚖️ Price vs Volume</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(charts.price_vs_volume(history),
                        width="stretch", key=f"pvv_{code}")

    st.caption(f"{pts} historical data points stored for {q.code} · "
               f"updated {q.captured_at.strftime('%I:%M:%S %p').lstrip('0')}")
