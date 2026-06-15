"""
components/charts.py
--------------------
Professional Plotly charts for the detailed stock analytics view.

All charts share a transparent dark theme so they sit cleanly on the
glass surfaces. Every function returns a ``go.Figure`` ready for
``st.plotly_chart``.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go

_GRID = "rgba(255,255,255,0.06)"
_FONT = "#9fb3d9"
_UP = "#34d399"
_DOWN = "#f87171"
_BLUE = "#60a5fa"
_VIOLET = "#c084fc"


def _theme(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=28, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_FONT, family="Inter, sans-serif"),
        hoverlabel=dict(bgcolor="#0f1830", bordercolor="#2a3a5e",
                        font=dict(color="#e8eefc")),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=_GRID, zeroline=False, title=None)
    fig.update_yaxes(gridcolor=_GRID, zeroline=False)
    return fig


def _empty(message: str = "No history yet") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False,
                       font=dict(color=_FONT, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _theme(fig, height=260)


def price_trend(df: pd.DataFrame, ycp: Optional[float] = None) -> go.Figure:
    """Live LTP line chart with a faint area fill and previous-close line."""
    if df is None or df.empty or "ltp" not in df:
        return _empty("No price history yet — it builds as the monitor runs")
    d = df.dropna(subset=["ltp"]).copy()
    if d.empty:
        return _empty()
    d["ts"] = pd.to_datetime(d["ts"])
    up = d["ltp"].iloc[-1] >= d["ltp"].iloc[0]
    color = _UP if up else _DOWN
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["ts"], y=d["ltp"], mode="lines",
        line=dict(color=color, width=2.6, shape="spline"),
        fill="tozeroy",
        fillcolor=("rgba(52,211,153,0.10)" if up else "rgba(248,113,113,0.10)"),
        hovertemplate="%{x|%d %b %I:%M %p}<br>LTP %{y:.2f} BDT<extra></extra>",
    ))
    if ycp:
        fig.add_hline(y=ycp, line_dash="dot", line_color="#7e93bb",
                      annotation_text="Prev close", annotation_font_color="#7e93bb")
    lo = min(d["ltp"].min(), ycp or d["ltp"].min())
    hi = max(d["ltp"].max(), ycp or d["ltp"].max())
    pad = (hi - lo) * 0.08 or 0.5
    fig.update_yaxes(range=[lo - pad, hi + pad], title="LTP (BDT)")
    return _theme(fig, 340)


def volume_trend(df: pd.DataFrame) -> go.Figure:
    """Bar chart of traded volume over time."""
    if df is None or df.empty or "volume" not in df:
        return _empty("No volume history yet")
    d = df.dropna(subset=["volume"]).copy()
    if d.empty:
        return _empty("No volume history yet")
    d["ts"] = pd.to_datetime(d["ts"])
    fig = go.Figure(go.Bar(
        x=d["ts"], y=d["volume"], marker_color=_BLUE,
        marker_line_width=0, opacity=0.85,
        hovertemplate="%{x|%d %b %I:%M %p}<br>Vol %{y:,.0f}<extra></extra>",
    ))
    fig.update_yaxes(title="Volume")
    return _theme(fig, 280)


def price_vs_volume(df: pd.DataFrame) -> go.Figure:
    """Combined chart: LTP line (left axis) + volume bars (right axis)."""
    if df is None or df.empty:
        return _empty()
    d = df.copy()
    d["ts"] = pd.to_datetime(d["ts"])
    fig = go.Figure()
    if "volume" in d:
        fig.add_trace(go.Bar(
            x=d["ts"], y=d["volume"], name="Volume", yaxis="y2",
            marker_color="rgba(96,165,250,0.35)", marker_line_width=0,
            hovertemplate="Vol %{y:,.0f}<extra></extra>",
        ))
    if "ltp" in d:
        fig.add_trace(go.Scatter(
            x=d["ts"], y=d["ltp"], name="LTP", mode="lines",
            line=dict(color=_VIOLET, width=2.6, shape="spline"),
            hovertemplate="LTP %{y:.2f}<extra></extra>",
        ))
    fig.update_layout(
        yaxis=dict(title="LTP (BDT)", gridcolor=_GRID),
        yaxis2=dict(title="Volume", overlaying="y", side="right",
                    showgrid=False),
    )
    return _theme(fig, 320)


def performance_gauge(change_pct: Optional[float]) -> go.Figure:
    """Bullish / Neutral / Bearish gauge driven by % change."""
    value = 0.0 if change_pct is None else max(-5.0, min(5.0, change_pct))
    if value > 0.3:
        bar = _UP
        label = "BULLISH"
    elif value < -0.3:
        bar = _DOWN
        label = "BEARISH"
    else:
        bar = _BLUE
        label = "NEUTRAL"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix="%", font=dict(size=30, color="#ffffff")),
        title=dict(text=label, font=dict(size=15, color=bar)),
        gauge=dict(
            axis=dict(range=[-5, 5], tickcolor=_FONT,
                      tickfont=dict(color=_FONT, size=10)),
            bar=dict(color=bar, thickness=0.28),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[-5, -1.5], color="rgba(248,113,113,0.18)"),
                dict(range=[-1.5, 1.5], color="rgba(96,165,250,0.14)"),
                dict(range=[1.5, 5], color="rgba(52,211,153,0.18)"),
            ],
            threshold=dict(line=dict(color="#ffffff", width=3),
                           thickness=0.8, value=value),
        ),
    ))
    fig.update_layout(
        height=240, margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color=_FONT, family="Inter"),
    )
    return fig


def day_range_bar(low: Optional[float], high: Optional[float],
                  ltp: Optional[float]) -> go.Figure:
    """Horizontal day-range indicator showing where LTP sits in low–high."""
    if None in (low, high) or high <= low:
        return _empty("Day range unavailable")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[low, high], y=[0, 0], mode="lines",
        line=dict(color="rgba(255,255,255,0.18)", width=10),
        hoverinfo="skip",
    ))
    if ltp is not None:
        fig.add_trace(go.Scatter(
            x=[ltp], y=[0], mode="markers+text",
            marker=dict(color=_VIOLET, size=18, line=dict(color="#fff", width=2)),
            text=[f"{ltp:g}"], textposition="top center",
            textfont=dict(color="#fff", size=13), hoverinfo="skip",
        ))
    fig.add_annotation(x=low, y=0, text=f"L {low:g}", showarrow=False,
                       yshift=-22, font=dict(color=_DOWN, size=11))
    fig.add_annotation(x=high, y=0, text=f"H {high:g}", showarrow=False,
                       yshift=-22, font=dict(color=_UP, size=11))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, range=[-1, 1])
    return _theme(fig, 130)
