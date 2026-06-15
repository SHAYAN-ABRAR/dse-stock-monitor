"""
views/overview.py
-----------------
Market Overview — the landing page. A live, breathing snapshot of the
whole Dhaka Stock Exchange: market breadth KPIs, top gainers / losers /
most-active, and a searchable table of every listed instrument with
one-click "add to dashboard".
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from runtime import flash, get_monitor, kpi_card, live_clock, pill
from utils import fmt_compact, fmt_money

monitor = get_monitor()
cfg = monitor.cfg

live_clock(cfg)


def _mover_rows(quotes, *, by, reverse, n=6):
    rows = ""
    for q in quotes[:n]:
        pct = q.change_pct
        direction = q.direction
        color = {"up": "#34d399", "down": "#f87171", "flat": "#93a9d4"}[direction]
        arrow = {"up": "▲", "down": "▼", "flat": "◆"}[direction]
        pct_str = f"{pct:+.2f}%" if pct is not None else "—"
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'<div><span style="font-weight:700;color:#fff;">{q.code}</span>'
            f'<span style="font-size:0.68rem;color:#7e93bb;margin-left:6px;">#{q.index}</span></div>'
            f'<div style="text-align:right;">'
            f'<span style="color:#dbe7ff;font-variant-numeric:tabular-nums;">{fmt_money(q.ltp)}</span>'
            f'<span style="color:{color};font-weight:700;margin-left:10px;">{arrow} {pct_str}</span>'
            f'</div></div>'
        )
    return rows


@st.fragment(run_every="15s")
def live_overview() -> None:
    quotes = monitor.all_quotes()
    if not quotes:
        st.warning("Market data is still loading. Use **⚡ Refresh now** "
                   "in the sidebar.")
        return

    traded = [q for q in quotes if q.ltp not in (None, 0)]
    adv = sum(1 for q in traded if (q.change or 0) > 0)
    dec = sum(1 for q in traded if (q.change or 0) < 0)
    unch = len(traded) - adv - dec
    total_value = sum((q.value_mn or 0) for q in quotes)
    total_volume = sum((q.volume or 0) for q in quotes)

    snap = monitor.snapshot()
    run_pill = pill("● LIVE", "green") if snap["running"] else pill("● PAUSED", "red")
    breadth = "green" if adv >= dec else "red"
    st.markdown(
        f'{run_pill}&nbsp;&nbsp;'
        f'{pill(f"▲ {adv} ADVANCING", "green")}&nbsp;&nbsp;'
        f'{pill(f"▼ {dec} DECLINING", "red")}&nbsp;&nbsp;'
        f'{pill(f"◆ {unch} UNCHANGED", "blue")}&nbsp;&nbsp;'
        f'{pill("MARKET " + ("BULLISH" if adv >= dec else "BEARISH"), breadth)}',
        unsafe_allow_html=True,
    )

    # ---- KPI strip ----
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("Listed Instruments", str(len(quotes)),
                         f"{len(traded)} traded today", "kpi-accent-blue"),
                unsafe_allow_html=True)
    k2.markdown(kpi_card("Market Breadth", f"{adv} / {dec}",
                         "advancers / decliners",
                         "kpi-accent-green" if adv >= dec else "kpi-accent-red"),
                unsafe_allow_html=True)
    k3.markdown(kpi_card("Total Turnover", f"{fmt_compact(total_value)}M",
                         "BDT value traded", "kpi-accent-violet"),
                unsafe_allow_html=True)
    k4.markdown(kpi_card("Total Volume", fmt_compact(total_volume),
                         "shares traded", "kpi-accent-amber"),
                unsafe_allow_html=True)

    # ---- Top movers ----
    movable = [q for q in traded if q.change_pct is not None]
    gainers = sorted(movable, key=lambda q: q.change_pct, reverse=True)
    losers = sorted(movable, key=lambda q: q.change_pct)
    active = sorted(traded, key=lambda q: (q.volume or 0), reverse=True)

    st.markdown('<div class="section-title">🔥 Market Movers</div>',
                unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown('<div class="glass-card" style="min-height:auto;padding-bottom:4px;">'
                    '<div class="kpi-label" style="color:#34d399;">Top Gainers</div>'
                    + _mover_rows(gainers, by="pct", reverse=True) + '</div>',
                    unsafe_allow_html=True)
    with m2:
        st.markdown('<div class="glass-card" style="min-height:auto;padding-bottom:4px;">'
                    '<div class="kpi-label" style="color:#f87171;">Top Losers</div>'
                    + _mover_rows(losers, by="pct", reverse=False) + '</div>',
                    unsafe_allow_html=True)
    with m3:
        st.markdown('<div class="glass-card" style="min-height:auto;padding-bottom:4px;">'
                    '<div class="kpi-label" style="color:#60a5fa;">Most Active (Volume)</div>'
                    + _mover_rows(active, by="vol", reverse=True) + '</div>',
                    unsafe_allow_html=True)

    st.caption(f"Live snapshot · {snap['stock_count']} stocks · "
               f"auto-refreshing every 15s · {snap['trading_hours_reason']}")


live_overview()

# ======================================================================
# Full searchable market table + add-to-dashboard
# ======================================================================
st.markdown('<div class="section-title">🔎 Browse All Stocks</div>',
            unsafe_allow_html=True)

quotes = monitor.all_quotes()
df = pd.DataFrame([{
    "#": q.index, "Code": q.code, "Sector": q.sector,
    "LTP": q.ltp, "Change": q.change, "Change %": q.change_pct,
    "Volume": q.volume, "Value (mn)": q.value_mn, "Trades": q.trades,
    "High": q.high, "Low": q.low,
} for q in quotes])

f1, f2 = st.columns([2, 1])
query = f1.text_input("Search by code, index number or sector",
                      placeholder="e.g. OLYMPIC · 260 · Bank", key="ov_search")
sectors = ["All sectors"] + sorted({q.sector for q in quotes})
sector = f2.selectbox("Sector", sectors, key="ov_sector")

view = df
if query.strip():
    ql = query.strip().lower()
    view = view[
        view["Code"].str.lower().str.contains(ql)
        | view["Sector"].str.lower().str.contains(ql)
        | view["#"].astype(str).eq(ql)
    ]
if sector != "All sectors":
    view = view[view["Sector"] == sector]

st.caption(f"Showing {len(view)} of {len(df)} instruments")
st.dataframe(
    view, width="stretch", hide_index=True, height=430,
    column_config={
        "#": st.column_config.NumberColumn(width="small"),
        "LTP": st.column_config.NumberColumn(format="%.2f"),
        "Change": st.column_config.NumberColumn(format="%.2f"),
        "Change %": st.column_config.NumberColumn(format="%.2f%%"),
        "Volume": st.column_config.NumberColumn(format="%d"),
        "Value (mn)": st.column_config.NumberColumn(format="%.2f"),
        "High": st.column_config.NumberColumn(format="%.2f"),
        "Low": st.column_config.NumberColumn(format="%.2f"),
    },
)

# ---- Quick add to dashboard ----
all_codes = [q.code for q in quotes]
selected = monitor.get_selected()
add = st.multiselect(
    "➕ Add stocks to your dashboard",
    options=all_codes, default=selected, key="ov_add",
    help="Selected stocks appear as live cards on **My Dashboard** and are "
         "tracked for history + alerts.")
# An empty multiselect never auto-wipes a non-empty selection (guards
# against Streamlit garbage-collecting the widget after a sidebar rerun).
if set(add) != set(selected) and (add or not selected):
    added = [c for c in add if c not in selected]
    removed = [c for c in selected if c not in add]
    monitor.set_selected(add)
    changes = ([(c, "added", "➕") for c in added]
               + [(c, "removed", "🗑") for c in removed])
    for code_, verb, icon in changes[:6]:
        flash(f"{code_} {verb}", icon)
    if len(changes) > 6:
        flash(f"+{len(changes) - 6} more changes", "ℹ️")

c1, c2 = st.columns([1, 4])
if c1.button("Open My Dashboard →", type="primary", width="stretch"):
    st.switch_page("views/dashboard.py")
