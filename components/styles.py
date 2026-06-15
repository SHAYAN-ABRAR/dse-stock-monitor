"""
components/styles.py
--------------------
Premium, client-ready visual theme for the whole platform.

A single ``inject()`` call drops the global CSS (glassmorphism backdrop,
animated stock cards, gradient accents, refined typography, custom
scrollbars and micro-interactions). Bloomberg / TradingView / Yahoo
Finance inspired — dark, frosted, alive.
"""

from __future__ import annotations

import streamlit as st

_GLOBAL_CSS = """
<style>
/* ============================ Typography ============================ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
}

/* ============================ Backdrop ============================== */
.stApp {
    background:
        radial-gradient(1200px 620px at 12% -5%, #1d3b66 0%, transparent 58%),
        radial-gradient(1050px 520px at 88% 4%, #3a1d63 0%, transparent 54%),
        radial-gradient(900px 700px at 50% 120%, #0f2a4a 0%, transparent 60%),
        linear-gradient(160deg, #070d18 0%, #0b1322 45%, #0c1526 100%);
    background-attachment: fixed;
    color: #e8eefc;
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.0rem; padding-bottom: 3rem; max-width: 1500px; }

/* Animated aurora sheen drifting across the very top */
.stApp::before {
    content: ""; position: fixed; top: -40%; left: -10%;
    width: 120%; height: 80%;
    background: radial-gradient(closest-side, rgba(99,102,241,0.10), transparent 70%);
    filter: blur(20px); pointer-events: none; z-index: 0;
    animation: aurora 18s ease-in-out infinite alternate;
}
@keyframes aurora {
    0%   { transform: translateX(-6%)  translateY(0)    scale(1);   opacity: 0.8; }
    100% { transform: translateX(10%)  translateY(3%)   scale(1.1); opacity: 1;   }
}

/* ============================ Scrollbars =========================== */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #3b4d77, #2a3a5e);
    border-radius: 999px; border: 2px solid transparent; background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover { background: #4d639a; }

/* ============================ Hero header ========================== */
.hero {
    position: relative; overflow: hidden;
    background: linear-gradient(120deg, rgba(96,165,250,0.16), rgba(168,85,247,0.13));
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 24px; padding: 1.5rem 2rem; margin-bottom: 1.3rem;
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    box-shadow: 0 18px 50px rgba(0,0,0,0.40);
}
.hero::after {
    content: ""; position: absolute; top: 0; left: -60%;
    width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent);
    transform: skewX(-20deg); animation: shimmer 7s ease-in-out infinite;
}
@keyframes shimmer { 0% { left: -60%; } 55%,100% { left: 130%; } }
.hero h1 {
    margin: 0; font-size: 1.85rem; font-weight: 800; letter-spacing: -0.01em;
    background: linear-gradient(90deg, #ffffff, #bcd3ff 60%, #d8c4ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p { margin: 0.45rem 0 0 0; color: #a6bbe0; font-size: 0.95rem; }

/* ============================ Glass KPI cards ====================== */
.glass-card {
    position: relative; overflow: hidden;
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.11);
    border-radius: 18px; padding: 1.05rem 1.25rem; min-height: 116px;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.32);
    transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.glass-card:hover {
    transform: translateY(-4px);
    border-color: rgba(255,255,255,0.22);
    box-shadow: 0 16px 44px rgba(0,0,0,0.46);
}
.glass-card .kpi-label {
    font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: #93a9d4; margin-bottom: 0.4rem; font-weight: 600;
}
.glass-card .kpi-value { font-size: 1.8rem; font-weight: 800; color: #fff; line-height: 1.1; }
.glass-card .kpi-sub { font-size: 0.78rem; color: #8ba1c9; margin-top: 0.35rem; }
.kpi-accent-green  .kpi-value { color: #34d399; }
.kpi-accent-red    .kpi-value { color: #f87171; }
.kpi-accent-amber  .kpi-value { color: #fbbf24; }
.kpi-accent-blue   .kpi-value { color: #60a5fa; }
.kpi-accent-violet .kpi-value { color: #c084fc; }
.glass-card.kpi-accent-green::before, .glass-card.kpi-accent-red::before,
.glass-card.kpi-accent-blue::before, .glass-card.kpi-accent-violet::before,
.glass-card.kpi-accent-amber::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}
.glass-card.kpi-accent-green::before  { background: linear-gradient(#34d399,#059669); }
.glass-card.kpi-accent-red::before    { background: linear-gradient(#f87171,#b91c1c); }
.glass-card.kpi-accent-blue::before   { background: linear-gradient(#60a5fa,#2563eb); }
.glass-card.kpi-accent-violet::before { background: linear-gradient(#c084fc,#7c3aed); }
.glass-card.kpi-accent-amber::before  { background: linear-gradient(#fbbf24,#d97706); }

/* ============================ Stock cards ========================= */
.stock-card {
    position: relative; overflow: hidden;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 20px; padding: 1.1rem 1.2rem 0.9rem 1.2rem;
    margin-bottom: 0.7rem;
    backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.30);
    transition: transform .28s cubic-bezier(.2,.8,.2,1), box-shadow .28s ease, border-color .28s ease;
    animation: cardIn .45s ease both;
}
/* spacer that separates one card unit (card + its buttons) from the next row */
.card-spacer { height: 22px; }
@keyframes cardIn { from { opacity: 0; transform: translateY(14px) scale(.98); } to { opacity: 1; transform: none; } }
.stock-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 22px 54px rgba(0,0,0,0.50);
    border-color: rgba(255,255,255,0.22);
}
.stock-card .sc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.stock-card .sc-idx {
    font-size: 0.68rem; color: #8ba1c9; font-weight: 700; letter-spacing: 0.08em;
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10);
    padding: 2px 8px; border-radius: 999px;
}
.stock-card .sc-code { font-size: 1.18rem; font-weight: 800; color: #fff; margin: 4px 0 0 0; letter-spacing: 0.01em; }
.stock-card .sc-sector { font-size: 0.68rem; color: #7e93bb; margin-top: 1px; text-transform: uppercase; letter-spacing: 0.06em; }
.stock-card .sc-ltp { font-size: 2.0rem; font-weight: 800; color: #fff; line-height: 1.0; margin: 0.55rem 0 0.15rem 0; font-variant-numeric: tabular-nums; }
.stock-card .sc-ltp small { font-size: 0.9rem; font-weight: 600; color: #93a9d4; }
.stock-card .sc-change { display: inline-flex; align-items: center; gap: 6px; font-size: 0.92rem; font-weight: 700; padding: 3px 10px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.sc-up   .sc-change { color: #34d399; background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.32); }
.sc-down .sc-change { color: #f87171; background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.32); }
.sc-flat .sc-change { color: #93a9d4; background: rgba(147,169,212,0.12); border: 1px solid rgba(147,169,212,0.30); }
.stock-card .sc-ltp { transition: color .2s ease; }
.sc-up   .sc-ltp { color: #eafff6; } .sc-down .sc-ltp { color: #fff0f0; }
.stock-card .sc-stats { display: flex; justify-content: space-between; gap: 6px; margin-top: 0.8rem; padding-top: 0.7rem; border-top: 1px solid rgba(255,255,255,0.08); }
.stock-card .sc-stat { text-align: center; flex: 1; }
.stock-card .sc-stat .v { font-size: 0.92rem; font-weight: 700; color: #dbe7ff; font-variant-numeric: tabular-nums; }
.stock-card .sc-stat .k { font-size: 0.62rem; color: #7e93bb; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.stock-card .sc-foot { font-size: 0.66rem; color: #6f85ad; margin-top: 0.7rem; display: flex; align-items: center; gap: 6px; }
/* left accent rail by direction */
.stock-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; }
.sc-up::before   { background: linear-gradient(#34d399,#059669); }
.sc-down::before { background: linear-gradient(#f87171,#b91c1c); }
.sc-flat::before { background: linear-gradient(#60a5fa,#3b82f6); }
/* soft glow on hover keyed to direction */
.sc-up:hover   { box-shadow: 0 22px 54px rgba(5,150,105,0.28); }
.sc-down:hover { box-shadow: 0 22px 54px rgba(185,28,28,0.28); }

.live-dot { width: 7px; height: 7px; border-radius: 50%; background: #34d399; display: inline-block; animation: dotBlink 1.6s ease-in-out infinite; }
@keyframes dotBlink { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }

/* ============================ Pills / badges ====================== */
.pill { display: inline-block; padding: 0.28rem 0.85rem; border-radius: 999px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.03em; }
.pill-green { background: rgba(52,211,153,0.14); color:#34d399; border:1px solid rgba(52,211,153,0.4); }
.pill-red   { background: rgba(248,113,113,0.14); color:#f87171; border:1px solid rgba(248,113,113,0.4); }
.pill-amber { background: rgba(251,191,36,0.14); color:#fbbf24; border:1px solid rgba(251,191,36,0.4); }
.pill-blue  { background: rgba(96,165,250,0.14); color:#60a5fa; border:1px solid rgba(96,165,250,0.4); }
.pill-violet{ background: rgba(192,132,252,0.14); color:#c084fc; border:1px solid rgba(192,132,252,0.4); }

.live-badge {
    display: inline-flex; align-items: center; gap: 0.55rem;
    background: linear-gradient(135deg, #ef4444, #b91c1c); color: #fff;
    font-weight: 800; font-size: 0.9rem; letter-spacing: 0.16em;
    padding: 0.5rem 1.3rem; border-radius: 999px; border: 1px solid rgba(255,255,255,0.25);
    animation: livePulse 1.6s ease-in-out infinite;
}
.live-badge .dot { width: 10px; height: 10px; border-radius: 50%; background: #fff; animation: dotBlink 1.6s ease-in-out infinite; }
@keyframes livePulse { 0%,100% { box-shadow: 0 0 8px rgba(239,68,68,0.45); } 50% { box-shadow: 0 0 26px rgba(239,68,68,0.95); } }

/* ============================ Section titles ====================== */
.section-title { font-size: 1.08rem; font-weight: 800; color: #e4ecff; margin: 1.1rem 0 0.6rem 0; letter-spacing: 0.01em; display:flex; align-items:center; gap:8px; }
.section-sub { font-size: 0.8rem; color: #8ba1c9; margin: -0.3rem 0 0.7rem 0; }

/* ============================ Buttons ============================= */
div.stButton > button, div.stDownloadButton > button {
    border-radius: 12px; font-weight: 700; border: 1px solid rgba(255,255,255,0.16);
    background: rgba(255,255,255,0.05); color: #e8eefc;
    backdrop-filter: blur(8px); padding: 0.5rem 1rem; transition: all .2s ease;
}
div.stButton > button:hover { transform: translateY(-2px); border-color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.09); }
div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; border: none; box-shadow: 0 6px 20px rgba(79,70,229,0.35); }
div.stButton > button[kind="primary"]:hover { filter: brightness(1.1); box-shadow: 0 10px 28px rgba(79,70,229,0.5); }
div.stButton > button:disabled { background: rgba(255,255,255,0.05) !important; color: #5b6b8a !important; border: 1px solid rgba(255,255,255,0.08) !important; cursor: not-allowed; transform: none !important; }

/* high-visibility refresh button */
.st-key-btn_refresh button {
    background: linear-gradient(135deg, #f59e0b, #dc2626) !important; color: #fff !important;
    border: 1px solid rgba(255,255,255,0.25) !important; font-weight: 800 !important;
    box-shadow: 0 0 16px rgba(220,38,38,0.4);
}
.st-key-btn_refresh button:hover { filter: brightness(1.12); box-shadow: 0 0 26px rgba(220,38,38,0.65); }

/* ============================ Inputs ============================= */
[data-testid="InputInstructions"] { display: none !important; }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.05) !important; border-radius: 11px !important;
    border: 1px solid rgba(255,255,255,0.12) !important; color: #e8eefc !important;
}
.stMultiSelect div[data-baseweb="tag"] { background: linear-gradient(135deg,#2563eb,#7c3aed) !important; border: none !important; }

/* ============================ Tabs / nav ========================= */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.stTabs [data-baseweb="tab"] { background: rgba(255,255,255,0.04); border-radius: 11px 11px 0 0; padding: 8px 16px; color: #a6bbe0; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, rgba(96,165,250,0.22), rgba(168,85,247,0.18)); color: #fff; }

/* ============================ Sidebar ============================ */
[data-testid="stSidebar"] { background: rgba(8,13,26,0.90); border-right: 1px solid rgba(255,255,255,0.07); backdrop-filter: blur(20px); }
[data-testid="stSidebar"] * { color: #dbe7ff; }
[data-testid="stSidebar"] .sb-brand { font-size: 1.2rem; font-weight: 800; letter-spacing: -0.01em;
    background: linear-gradient(90deg,#60a5fa,#c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

/* ============================ Dataframe ========================== */
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); }

/* ============================ Top toast ========================= */
/* Slides down from the top, holds ~1.5s, slides back up and vanishes. */
@keyframes topToast {
    0%   { transform: translate(-50%, -160%); opacity: 0; }
    11%  { transform: translate(-50%, 0);     opacity: 1; }
    12%  { transform: translate(-50%, 4px);   opacity: 1; }  /* tiny settle */
    14%  { transform: translate(-50%, 0);     opacity: 1; }
    86%  { transform: translate(-50%, 0);     opacity: 1; }
    100% { transform: translate(-50%, -160%); opacity: 0; }
}
.top-toast {
    position: fixed; top: 18px; left: 50%; z-index: 100000;
    transform: translate(-50%, -160%);
    display: inline-flex; align-items: center; gap: 9px;
    padding: 0.72rem 1.5rem; border-radius: 999px;
    font-size: 0.95rem; font-weight: 700; color: #ffffff; white-space: nowrap;
    background: linear-gradient(135deg, rgba(37,99,235,0.96), rgba(124,58,237,0.96));
    border: 1px solid rgba(255,255,255,0.28);
    box-shadow: 0 14px 40px rgba(79,70,229,0.45), 0 0 0 1px rgba(255,255,255,0.06) inset;
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    pointer-events: none; opacity: 0;
    animation: topToast 2s cubic-bezier(.16,.84,.32,1) both;
}
.top-toast .tt-ico { font-size: 1.05rem; }

/* ============================ Misc ============================== */
.error-banner { background: linear-gradient(135deg, rgba(248,113,113,0.20), rgba(248,113,113,0.07)); border: 1px solid rgba(248,113,113,0.5); border-radius: 16px; padding: 0.9rem 1.2rem; color: #fecaca; font-weight: 600; margin-bottom: 1rem; }
.muted { color: #8ba1c9; font-size: 0.82rem; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.detail-cell { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.09); border-radius: 13px; padding: 0.7rem 0.85rem; }
.detail-cell .k { font-size: 0.66rem; color: #8ba1c9; text-transform: uppercase; letter-spacing: 0.07em; }
.detail-cell .v { font-size: 1.12rem; font-weight: 700; color: #fff; margin-top: 3px; font-variant-numeric: tabular-nums; }
</style>
"""


def inject() -> None:
    """Inject the global premium theme once per page render."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)
