"""
components/styles.py
--------------------
Premium, client-ready visual theme for the whole platform — now with a
fully self-contained **dark + light** theme system.

``inject(theme)`` drops the global CSS. Every surface, text colour, border
and widget internal (inputs, dropdown menus, popover panels, dialogs) is
driven by CSS custom properties whose values are swapped per theme. This
makes the app's appearance authoritative regardless of the visitor's OS /
browser colour scheme — so the form boxes can never end up light while the
site is dark (or vice-versa).
"""

from __future__ import annotations

import streamlit as st

# ----------------------------------------------------------------------
# Theme palettes. The dark values reproduce the original look exactly;
# the light values are a soft, frosted daylight variant. Accent colours
# (green/red/blue/violet/amber) are identical in both themes and stay as
# literals in the CSS below.
# ----------------------------------------------------------------------
_PALETTES = {
    "dark": {
        "color-scheme": "dark",
        "app-bg": (
            "radial-gradient(1200px 620px at 12% -5%, #1d3b66 0%, transparent 58%),"
            "radial-gradient(1050px 520px at 88% 4%, #3a1d63 0%, transparent 54%),"
            "radial-gradient(900px 700px at 50% 120%, #0f2a4a 0%, transparent 60%),"
            "linear-gradient(160deg, #070d18 0%, #0b1322 45%, #0c1526 100%)"
        ),
        "text": "#e8eefc",
        "text-strong": "#ffffff",
        "text-muted": "#8ba1c9",
        "text-faint": "#6f85ad",
        "surface": "rgba(255,255,255,0.05)",
        "surface-2": "rgba(255,255,255,0.09)",
        "surface-3": "rgba(255,255,255,0.13)",
        "surface-inset": "rgba(255,255,255,0.035)",
        "border": "rgba(255,255,255,0.11)",
        "border-2": "rgba(255,255,255,0.22)",
        "input-bg": "rgba(255,255,255,0.05)",
        "input-text": "#e8eefc",
        "menu-bg": "#0f1830",
        "sidebar-bg": "rgba(8,13,26,0.90)",
        "shadow-card": "rgba(0,0,0,0.32)",
        "shadow-strong": "rgba(0,0,0,0.50)",
        "hero-grad": "linear-gradient(120deg, rgba(96,165,250,0.16), rgba(168,85,247,0.13))",
        "hero-title-grad": "linear-gradient(90deg, #ffffff, #bcd3ff 60%, #d8c4ff)",
        "scroll-track": "rgba(255,255,255,0.03)",
        "scroll-thumb": "linear-gradient(180deg, #3b4d77, #2a3a5e)",
        "band-btn-bg": "rgba(124,58,237,0.16)",
        "band-btn-text": "#d8c8ff",
        "band-btn-border": "rgba(168,85,247,0.34)",
        # nav→brand separator: invisible in dark (theme left untouched)
        "nav-sep-color": "transparent",
        "nav-sep-pad": "0rem",
    },
    "light": {
        "color-scheme": "light",
        # Airy, premium daylight backdrop — soft blue/violet light leaks on a
        # near-white canvas (Stripe / Linear style), not flat grey.
        "app-bg": (
            "radial-gradient(1100px 560px at 8% -8%, #e7f0ff 0%, transparent 56%),"
            "radial-gradient(980px 520px at 92% -4%, #f1eaff 0%, transparent 52%),"
            "radial-gradient(1000px 760px at 50% 122%, #e6f0ff 0%, transparent 60%),"
            "linear-gradient(160deg, #f7fafe 0%, #eef3fb 55%, #e8eef8 100%)"
        ),
        "text": "#18253e",
        "text-strong": "#0a1322",
        "text-muted": "#5b6a88",
        "text-faint": "#8a9ab6",
        # Crisp frosted-white cards with cool soft shadows for real depth.
        "surface": "rgba(255,255,255,0.86)",
        "surface-2": "#eef3fb",
        "surface-3": "#e5edf8",
        "surface-inset": "#f3f7fd",
        "border": "rgba(18,38,73,0.10)",
        "border-2": "rgba(18,38,73,0.20)",
        "input-bg": "#ffffff",
        "input-text": "#15233f",
        "menu-bg": "#ffffff",
        "sidebar-bg": "rgba(255,255,255,0.82)",
        "shadow-card": "rgba(43,67,120,0.10)",
        "shadow-strong": "rgba(43,67,120,0.20)",
        "hero-grad": "linear-gradient(120deg, rgba(96,165,250,0.22), rgba(168,85,247,0.16))",
        "hero-title-grad": "linear-gradient(90deg, #1e3a8a, #4338ca 55%, #7c3aed)",
        "scroll-track": "rgba(20,40,80,0.05)",
        "scroll-thumb": "linear-gradient(180deg, #c3d0e6, #a7b7d6)",
        "band-btn-bg": "rgba(124,58,237,0.10)",
        "band-btn-text": "#6d28d9",
        "band-btn-border": "rgba(124,58,237,0.30)",
        # nav→brand separator: a subtle line above the brand in light mode
        "nav-sep-color": "rgba(18,38,73,0.16)",
        "nav-sep-pad": "0.7rem",
    },
}


# ----------------------------------------------------------------------
# The CSS template. All theme-dependent values reference var(--…); accent
# colours are kept literal because they read well on both backgrounds.
# ----------------------------------------------------------------------
_BASE_CSS = """
/* ============================ Typography ============================ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
}
:root { color-scheme: var(--color-scheme); }

/* ============================ Backdrop ============================== */
.stApp {
    background: var(--app-bg);
    background-attachment: fixed;
    color: var(--text);
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
::-webkit-scrollbar-track { background: var(--scroll-track); }
::-webkit-scrollbar-thumb {
    background: var(--scroll-thumb);
    border-radius: 999px; border: 2px solid transparent; background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover { filter: brightness(1.15); }

/* ============================ Hero header ========================== */
.hero {
    position: relative; overflow: hidden;
    background: var(--hero-grad);
    border: 1px solid var(--border);
    border-radius: 18px; padding: 0.85rem 1.4rem; margin-bottom: 1.0rem;
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    box-shadow: 0 18px 50px var(--shadow-card);
}
.hero::after {
    content: ""; position: absolute; top: 0; left: -60%;
    width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent);
    transform: skewX(-20deg); animation: shimmer 7s ease-in-out infinite;
}
@keyframes shimmer { 0% { left: -60%; } 55%,100% { left: 130%; } }
.hero h1 {
    margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em;
    background: var(--hero-title-grad);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p { margin: 0.2rem 0 0 0; color: var(--text-muted); font-size: 0.85rem; }

/* ============================ Glass KPI cards ====================== */
.glass-card {
    position: relative; overflow: hidden;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px; padding: 1.05rem 1.25rem; min-height: 116px;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 30px var(--shadow-card);
    transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.glass-card:hover {
    transform: translateY(-4px);
    border-color: var(--border-2);
    box-shadow: 0 16px 44px var(--shadow-strong);
}
.glass-card .kpi-label {
    font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;
}
.glass-card .kpi-value { font-size: 1.8rem; font-weight: 800; color: var(--text-strong); line-height: 1.1; }
.glass-card .kpi-sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.35rem; }
.kpi-accent-green  .kpi-value { color: #10b981; }
.kpi-accent-red    .kpi-value { color: #ef4444; }
.kpi-accent-amber  .kpi-value { color: #d97706; }
.kpi-accent-blue   .kpi-value { color: #2563eb; }
.kpi-accent-violet .kpi-value { color: #7c3aed; }
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
/* The dashboard card is a real Streamlit container (keyed st-key-card_*)
   so the band setter + hit counter live INSIDE the card. Sized compact so
   FOUR cards fit per row without dropping information. */
div[class*="st-key-card_"] {
    position: relative; overflow: hidden;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    padding: 0.8rem 0.9rem 0.7rem 1.05rem !important;
    backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
    box-shadow: 0 10px 30px var(--shadow-card);
    transition: box-shadow .28s ease, border-color .28s ease;
    animation: cardIn .45s ease both;
}
div[class*="st-key-card_"]:hover {
    box-shadow: 0 22px 54px var(--shadow-strong);
    border-color: var(--border-2);
}
div[class*="st-key-card_"] [data-testid="stVerticalBlock"] { gap: 0.45rem; }
div[class*="st-key-card_"]::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; z-index:2; }
div[class*="st-key-card_up_"]::before   { background: linear-gradient(#34d399,#059669); }
div[class*="st-key-card_down_"]::before { background: linear-gradient(#f87171,#b91c1c); }
div[class*="st-key-card_flat_"]::before { background: linear-gradient(#60a5fa,#3b82f6); }
div[class*="st-key-card_up_"]:hover   { box-shadow: 0 22px 54px rgba(5,150,105,0.26); }
div[class*="st-key-card_down_"]:hover { box-shadow: 0 22px 54px rgba(185,28,28,0.26); }

.card-spacer { height: 12px; }
@keyframes cardIn { from { opacity: 0; transform: translateY(14px) scale(.98); } to { opacity: 1; transform: none; } }

.sc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.sc-idx {
    font-size: 0.60rem; color: var(--text-muted); font-weight: 700; letter-spacing: 0.08em;
    background: var(--surface-2); border: 1px solid var(--border);
    padding: 1px 7px; border-radius: 999px;
}
.sc-code { font-size: 1.05rem; font-weight: 800; color: var(--text-strong); margin: 2px 0 0 0; letter-spacing: 0.01em; }
.sc-sector { font-size: 0.60rem; color: var(--text-faint); margin-top: 1px; text-transform: uppercase; letter-spacing: 0.06em; white-space: nowrap; }
.sc-ltp { font-size: 1.55rem; font-weight: 800; color: var(--text-strong); line-height: 1.0; margin: 0; font-variant-numeric: tabular-nums; transition: color .2s ease; white-space: nowrap; }
.sc-ltp small { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); }
.sc-change { display: inline-flex; align-items: center; font-size: 0.70rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.sc-change.dir-up   { color: #10b981; background: rgba(52,211,153,0.14); border: 1px solid rgba(52,211,153,0.34); }
.sc-change.dir-down { color: #ef4444; background: rgba(248,113,113,0.14); border: 1px solid rgba(248,113,113,0.34); }
.sc-change.dir-flat { color: #3b82f6; background: rgba(96,165,250,0.14); border: 1px solid rgba(96,165,250,0.32); }
.sc-foot {
    font-size: 0.62rem; color: var(--text-faint); margin-top: 0.45rem;
    padding-top: 0.45rem; border-top: 1px solid var(--border);
    display: flex; align-items: center; gap: 6px;
}

/* ============== Dashboard card: LTP band + hit counter ============ */
/* The band setter is a compact popover (dropdown) trigger to save space. */
div[class*="st-key-bandpop_"] { margin-top: 0.1rem; }
div[class*="st-key-bandpop_"] button {
    width: 100% !important;
    background: var(--band-btn-bg) !important;
    border: 1px solid var(--band-btn-border) !important;
    color: var(--band-btn-text) !important; font-weight: 700 !important;
    border-radius: 10px !important; justify-content: center !important;
    padding: 0.28rem 0.6rem !important; min-height: 2rem !important;
}
div[class*="st-key-bandpop_"] button p { font-size: 0.8rem !important; }
/* Compact in-card controls so four cards fit per row */
div[class*="st-key-card_"] div.stButton button {
    padding: 0.28rem 0.6rem; min-height: 2rem; border-radius: 10px;
}
div[class*="st-key-card_"] div.stButton button p { font-size: 0.82rem !important; }
/* Emoji glyphs (🔔/✕/🎯) are drawn TALLER than their font-size line box, and
   the button's inner markdown container clips overflow — which sliced the
   bell in half. Let the glyphs overflow and give them room to breathe. */
div[class*="st-key-card_"] div.stButton button [data-testid="stMarkdownContainer"],
div[class*="st-key-card_"] div.stButton button p,
div[class*="st-key-bandpop_"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-bandpop_"] button p {
    overflow: visible !important; line-height: 1.35 !important;
}
/* Per-card notification bell (YouTube-style): amber when armed, dim when
   muted. The label is a Material-symbol icon, so it sizes exactly. */
div[class*="_bell_on_"] button, div[class*="_bell_off_"] button {
    padding: 0.28rem 0.3rem;
}
div[class*="_bell_on_"] button [data-testid="stIconMaterial"],
div[class*="_bell_off_"] button [data-testid="stIconMaterial"] {
    font-size: 1.15rem; line-height: 1;
}
div[class*="_bell_on_"] button {
    background: rgba(245,158,11,0.16) !important;
    border: 1px solid rgba(245,158,11,0.50) !important;
}
div[class*="_bell_on_"] button [data-testid="stIconMaterial"] { color: #d97706 !important; }
div[class*="_bell_on_"] button:hover { background: rgba(245,158,11,0.26) !important; }
div[class*="_bell_off_"] button { opacity: 0.65; }
div[class*="st-key-bandpop_"] button:hover {
    filter: brightness(1.08);
    border-color: var(--band-btn-border) !important;
    transform: translateY(-1px);
}
.band-head {
    display: flex; align-items: center; gap: 7px;
    font-size: 0.74rem; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.45rem;
}
.band-ico { font-size: 0.98rem; }
[data-testid="stPopoverBody"] [data-testid="stNumberInput"] label {
    font-size: 0.72rem !important; color: var(--text-muted) !important; font-weight: 600 !important;
}
[data-testid="stPopoverBody"] input { font-weight: 700 !important; }
/* Multi-condition picker: compact checkbox rows (one per condition).
   The label text lives in a <p> INSIDE the label, and Streamlit paints it
   directly with the pinned dark theme's near-white — colouring the label
   alone can't reach it (a direct colour beats inheritance), so recolour
   the descendants too or the words vanish on the light popover. */
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] { gap: 0.45rem; }
[data-testid="stPopoverBody"] .stCheckbox label { padding: 0.05rem 0; }
[data-testid="stPopoverBody"] .stCheckbox label p,
[data-testid="stPopoverBody"] .stCheckbox label * {
    color: var(--text-strong) !important;
}
[data-testid="stPopoverBody"] .stCheckbox label p {
    font-size: 0.82rem !important; font-weight: 600 !important;
}

/* Price row: LTP left, change pill right — always one line each */
.sc-pricerow {
    display: flex; align-items: center; justify-content: space-between;
    gap: 8px; margin: 0.4rem 0 0.15rem 0;
}
/* The 'times hit' counter: a full-width strip under the price made of two
   fixed single-line rows (title + state chip, then count + condition), so
   nothing ever wraps or clips and every card keeps the same height. */
.hit-box {
    position: relative;
    border-radius: 12px; padding: 0.45rem 0.6rem; margin-top: 0.25rem;
    background: var(--surface-inset);
    border: 1px solid var(--border);
    transition: border-color .25s ease, box-shadow .25s ease;
}
.hit-box .hit-top { display: flex; align-items: center; gap: 5px; min-width: 0; }
.hit-box .hit-icon { font-size: 0.85rem; }
.hit-box .hit-title {
    font-size: 0.60rem; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-muted); white-space: nowrap;
}
.hit-box .hit-chip {
    margin-left: auto; flex: 0 0 auto; font-size: 0.56rem; font-weight: 800;
    letter-spacing: 0.03em; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
}
.hit-box .hit-row { display: flex; align-items: baseline; gap: 8px; margin-top: 2px; min-width: 0; }
.hit-box .hit-row + .hit-row { margin-top: 4px; }
.hit-box .chip-in { color: #10b981; background: rgba(52,211,153,0.16); border: 1px solid rgba(52,211,153,0.40); }
.hit-box .chip-out { color: var(--text-muted); background: var(--surface-2); border: 1px solid var(--border); }
.hit-box .hit-count {
    font-size: 1.3rem; font-weight: 900; line-height: 1.0;
    font-variant-numeric: tabular-nums;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hit-box .hit-sub {
    font-size: 0.62rem; color: var(--text-muted); min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.hit-box.hit-in { border-color: rgba(52,211,153,0.45); box-shadow: 0 0 18px rgba(52,211,153,0.16); }
/* green count only on the row(s) whose condition is satisfied right now */
.hit-box .hit-row.row-in .hit-count {
    background: linear-gradient(90deg, #10b981, #059669);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hit-box.hit-unset .hit-count { background: none; -webkit-text-fill-color: var(--text-faint); color: var(--text-faint); }

/* ============================ Pills / badges ====================== */
.pill { display: inline-block; padding: 0.28rem 0.85rem; border-radius: 999px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.03em; }
.pill-green { background: rgba(16,185,129,0.15); color:#10b981 !important; border:1px solid rgba(16,185,129,0.4); }
.pill-red   { background: rgba(239,68,68,0.15);  color:#ef4444 !important; border:1px solid rgba(239,68,68,0.4); }
.pill-amber { background: rgba(217,119,6,0.15);  color:#d97706 !important; border:1px solid rgba(217,119,6,0.4); }
.pill-blue  { background: rgba(37,99,235,0.15);  color:#2563eb !important; border:1px solid rgba(37,99,235,0.4); }
.pill-violet{ background: rgba(124,58,237,0.15); color:#7c3aed !important; border:1px solid rgba(124,58,237,0.4); }

.live-badge {
    display: inline-flex; align-items: center; gap: 0.55rem;
    background: linear-gradient(135deg, #ef4444, #b91c1c); color: #fff;
    font-weight: 800; font-size: 0.9rem; letter-spacing: 0.16em;
    padding: 0.5rem 1.3rem; border-radius: 999px; border: 1px solid rgba(255,255,255,0.25);
    animation: livePulse 1.6s ease-in-out infinite;
}
.live-badge .dot { width: 10px; height: 10px; border-radius: 50%; background: #fff; animation: dotBlink 1.6s ease-in-out infinite; }
@keyframes livePulse { 0%,100% { box-shadow: 0 0 8px rgba(239,68,68,0.45); } 50% { box-shadow: 0 0 26px rgba(239,68,68,0.95); } }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: #10b981; display: inline-block; animation: dotBlink 1.6s ease-in-out infinite; }
@keyframes dotBlink { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }

/* ============================ Section titles ====================== */
.section-title { font-size: 1.08rem; font-weight: 800; color: var(--text-strong); margin: 1.1rem 0 0.6rem 0; letter-spacing: 0.01em; display:flex; align-items:center; gap:8px; }
.section-sub { font-size: 0.8rem; color: var(--text-muted); margin: -0.3rem 0 0.7rem 0; }

/* ---- Section dividers (st.divider) — a clear, themed separating line in
        BOTH dark and light mode ---- */
hr, [data-testid="stMarkdownContainer"] hr, [data-testid="stSidebar"] hr {
    border: none !important;
    border-top: 1px solid var(--border-2) !important;
    background-color: transparent !important;
    height: 0 !important; margin: 0.75rem 0 !important;
}

/* ============================ Buttons ============================= */
/* NOTE: use a descendant selector (not '>') — buttons with a help tooltip
   get wrapped in an extra element, which would otherwise dodge the theme
   and fall back to the dark base style (the "black ✕ button" bug). */
div.stButton button, div.stDownloadButton button {
    border-radius: 12px; font-weight: 700; border: 1px solid var(--border);
    background: var(--surface); color: var(--text);
    backdrop-filter: blur(8px); padding: 0.5rem 1rem; transition: all .2s ease;
}
div.stButton button:hover { transform: translateY(-2px); border-color: var(--border-2); background: var(--surface-2); }
div.stButton button[kind="primary"] { background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; border: none; box-shadow: 0 6px 20px rgba(79,70,229,0.35); }
div.stButton button[kind="primary"]:hover { filter: brightness(1.1); box-shadow: 0 10px 28px rgba(79,70,229,0.5); }
/* The button caption is a nested <p>, and broad text rules (the sidebar's
   `p`, the dialog's `*`) colour that <p> DIRECTLY — beating the white the
   button would hand down by inheritance. On gradient buttons that meant
   dark-on-purple text in light mode, so force every descendant white. */
div.stButton button[kind="primary"] *, div.stDownloadButton button[kind="primary"] * { color: #fff !important; }
div.stButton button:disabled { background: var(--surface) !important; color: var(--text-faint) !important; border: 1px solid var(--border) !important; cursor: not-allowed; transform: none !important; }

/* high-visibility refresh button */
.st-key-btn_refresh button {
    background: linear-gradient(135deg, #f59e0b, #dc2626) !important; color: #fff !important;
    border: 1px solid rgba(255,255,255,0.25) !important; font-weight: 800 !important;
    box-shadow: 0 0 16px rgba(220,38,38,0.4);
}
.st-key-btn_refresh button:hover { filter: brightness(1.12); box-shadow: 0 0 26px rgba(220,38,38,0.65); }
.st-key-btn_refresh button * { color: #fff !important; }

/* ============================ Inputs ============================= */
[data-testid="InputInstructions"] { display: none !important; }
.stTextInput input, .stNumberInput input, .stTextArea textarea,
.stDateInput input, .stTimeInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"] {
    background: var(--input-bg) !important; border-radius: 11px !important;
    border: 1px solid var(--border) !important; color: var(--input-text) !important;
}
.stTextInput input, .stNumberInput input, .stTextArea textarea { color: var(--input-text) !important; }
div[data-baseweb="select"] *, div[data-baseweb="input"] * { color: var(--input-text) !important; }
/* Multiselect tags: match on the attribute alone — newer Streamlit renders
   the tag as a <span>, not a <div>, and a div-only selector silently stops
   applying (leaving primary-purple tags with the input's dark text). */
.stMultiSelect [data-baseweb="tag"], [data-testid="stMultiSelect"] [data-baseweb="tag"] { background: linear-gradient(135deg,#2563eb,#7c3aed) !important; border: none !important; color:#fff !important; }
.stMultiSelect [data-baseweb="tag"] *, [data-testid="stMultiSelect"] [data-baseweb="tag"] * { color:#fff !important; fill:#fff !important; }
/* placeholder + value text */
input::placeholder, textarea::placeholder { color: var(--text-faint) !important; }

/* ---- Portaled baseweb surfaces (st.popover, selectbox/multiselect menus,
        tooltips). These render in a layer on <body>, and their dark fill is
        baseweb's DEFAULT surface colour (Streamlit's secondaryBackground),
        which sits on the layer OR a wrapper — NOT necessarily on the element
        we can name. So we paint the layer's child + the body + (modern) the
        layer itself, all to the theme's menu colour. ---- */
div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] [data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] {
    background-color: var(--menu-bg) !important;
    color: var(--text) !important;
    border-radius: 16px;
}
div[data-baseweb="popover"]:has([data-testid="stPopoverBody"]) {
    background-color: var(--menu-bg) !important; border-radius: 16px;
}
[data-testid="stPopoverBody"] {
    border: 1px solid var(--border) !important;
    box-shadow: 0 18px 50px var(--shadow-strong) !important;
}
/* keep inner layout blocks transparent so only the panel paints the bg */
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
[data-testid="stPopoverBody"] [data-testid="stHorizontalBlock"],
[data-testid="stPopoverBody"] [data-testid="stElementContainer"] { background: transparent !important; }

/* Dropdown option lists — selectbox & multiselect use a VIRTUALIZED list
   (testid stSelectboxVirtualDropdown) inside a popover wrapper, plus the
   baseweb <ul role="listbox">. Paint the wrapper + list + the dropdown. */
[data-baseweb="popover"]:has([data-testid="stSelectboxVirtualDropdown"]),
[data-baseweb="popover"]:has([data-testid="stSelectboxVirtualDropdown"]) > div,
[data-testid="stSelectboxVirtualDropdown"],
[role="listbox"], ul[data-baseweb="menu"], div[data-baseweb="menu"] {
    background-color: var(--menu-bg) !important; color: var(--text) !important;
    border-color: var(--border) !important; border-radius: 12px;
}
[role="listbox"], ul[data-baseweb="menu"] { border: 1px solid var(--border) !important; }
/* themed text for every item in the virtualized dropdown (non-important so
   the hover/selected rules below still win) */
[data-testid="stSelectboxVirtualDropdown"] * { color: var(--text); }
[role="option"], ul[data-baseweb="menu"] li {
    background-color: transparent !important; color: var(--text) !important;
}
[role="option"]:hover, ul[data-baseweb="menu"] li:hover,
[role="option"][aria-selected="true"] {
    background-color: var(--surface-2) !important; color: var(--text-strong) !important;
}

/* Header ⋮ main-menu popover */
[data-testid="stMainMenuPopover"], [data-testid="stMainMenuList"] {
    background-color: var(--menu-bg) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important;
}
[data-testid="stMainMenuList"] li, [data-testid="stMainMenuList"] [role="option"],
[data-testid="stMainMenuItemLabel"] { color: var(--text) !important; }
[data-testid="stMainMenuList"] li:hover { background-color: var(--surface-2) !important; }
/* tooltips */
div[data-baseweb="tooltip"] { background: var(--menu-bg) !important; color: var(--text) !important; }
/* modal dialogs (st.dialog / confirm modal) — also portaled */
div[role="dialog"], [data-testid="stDialog"] > div,
[data-testid="stDialog"] [role="dialog"],
[data-testid="stDialog"] div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--menu-bg) !important; color: var(--text) !important;
    border-color: var(--border) !important;
}
[data-testid="stDialog"] [data-testid="stVerticalBlock"] { background: transparent !important; }
/* dialog text follows the theme (non-important so primary buttons stay white) */
[data-testid="stDialog"] * { color: var(--text); }

/* widget labels + captions follow the theme */
[data-testid="stWidgetLabel"] label, [data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"], .stCheckbox label, .stRadio label, .stToggle label {
    color: var(--text) !important;
}
/* Radio/checkbox/toggle OPTION text: Streamlit colours the inner text node
   directly (pinned dark theme's near-white), so the label rules above never
   reach it — recolour the descendants or the words vanish in light mode.
   The popover-scoped rule (higher specificity) still wins inside popovers. */
[data-testid="stRadio"] [role="radiogroup"] label *,
.stCheckbox label p, .stToggle label p {
    color: var(--text) !important;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--text-muted) !important; }

/* ============================ Tabs / nav ========================= */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { background: var(--surface); border-radius: 11px 11px 0 0; padding: 8px 16px; color: var(--text-muted); }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, rgba(96,165,250,0.22), rgba(168,85,247,0.18)); color: var(--text-strong); }

/* ============================ Sidebar ============================ */
[data-testid="stSidebar"] { background: var(--sidebar-bg); border-right: 1px solid var(--border); backdrop-filter: blur(20px); }
[data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: var(--text); }
[data-testid="stSidebar"] .sb-brand { font-size: 1.2rem; font-weight: 800; letter-spacing: -0.01em;
    background: linear-gradient(90deg,#60a5fa,#c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    border-top: 1px solid var(--nav-sep-color); padding-top: var(--nav-sep-pad); }

/* ---- Sun / moon theme toggle (a fully restyled st.button switch) ---- */
.theme-label {
    font-weight: 700; font-size: 0.9rem; color: var(--text);
    display: flex; align-items: center; height: 38px; white-space: nowrap;
}
div[class*="st-key-theme_toggle_"] { display: flex; justify-content: flex-end; }
div[class*="st-key-theme_toggle_"] button {
    position: relative; width: 76px !important; min-width: 76px !important;
    height: 36px !important; padding: 0 !important; border-radius: 999px !important;
    overflow: hidden; cursor: pointer;
    border: 1px solid var(--border-2) !important;
    box-shadow: inset 0 2px 7px rgba(0,0,0,0.38);
    transition: filter .25s ease, box-shadow .25s ease;
}
div[class*="st-key-theme_toggle_"] button p,
div[class*="st-key-theme_toggle_"] button [data-testid="stMarkdownContainer"] {
    display: none !important;                 /* hide the accessible label text */
}
div[class*="st-key-theme_toggle_"] button:hover {
    transform: none !important; filter: brightness(1.07);
    box-shadow: inset 0 2px 7px rgba(0,0,0,0.38), 0 0 14px rgba(124,58,237,0.35);
}
/* track backgrounds: night sky vs day sky */
.st-key-theme_toggle_dark button  { background: linear-gradient(135deg,#27314c,#0d1426) !important; }
.st-key-theme_toggle_light button { background: linear-gradient(135deg,#bfe1ff,#ffe39a) !important; }
/* the sliding knob (holds the active icon) */
div[class*="st-key-theme_toggle_"] button::before {
    position: absolute; top: 4px; width: 27px; height: 27px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; line-height: 27px; text-align: center;
    box-shadow: 0 2px 7px rgba(0,0,0,0.45);
    animation: knobPop .38s cubic-bezier(.2,.85,.25,1);
}
.st-key-theme_toggle_dark button::before  { content: "🌙"; right: 4px; background: radial-gradient(circle at 35% 30%, #1b2740, #0a1020); }
.st-key-theme_toggle_light button::before { content: "☀️"; left: 4px;  background: radial-gradient(circle at 35% 30%, #ffffff, #fff2cc); }
/* faint hint of the other mode on the empty side */
div[class*="st-key-theme_toggle_"] button::after {
    position: absolute; top: 0; height: 36px; line-height: 36px; font-size: 13px; opacity: 0.5;
}
.st-key-theme_toggle_dark button::after  { content: "☀️"; left: 10px; }
.st-key-theme_toggle_light button::after { content: "🌙"; right: 10px; }
@keyframes knobPop { from { transform: scale(.45) translateX(var(--knob-from,0)); opacity: .25; } to { transform: scale(1); opacity: 1; } }

/* ============ Native Streamlit chrome — keep glyphs visible ========= */
/* Streamlit's own icons (nav symbols, chevrons, steppers, menu) carry a
   colour tied to the (pinned dark) base theme, so on a light background
   they'd be near-invisible. Force every one of them to the active theme's
   text colour. Status-accent icons keep their colour (handled below). */

/* Sidebar navigation: page icons + labels + the active item */
[data-testid="stSidebarNav"] a { color: var(--text) !important; border-radius: 10px; }
[data-testid="stSidebarNav"] a span,
[data-testid="stSidebarNav"] a p,
[data-testid="stSidebarNav"] a [data-testid="stIconMaterial"] { color: var(--text) !important; }
[data-testid="stSidebarNav"] a:hover { background: var(--surface-2) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--surface-2) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] span,
[data-testid="stSidebarNav"] a[aria-current="page"] p,
[data-testid="stSidebarNav"] a[aria-current="page"] [data-testid="stIconMaterial"] { color: var(--text-strong) !important; }

/* Any material icon in the sidebar (e.g. the settings gear) */
[data-testid="stSidebar"] [data-testid="stIconMaterial"] { color: var(--text-muted) !important; }

/* Header bar: main menu (⋮), deploy, sidebar collapse/expand controls */
[data-testid="stToolbar"] [data-testid="stIconMaterial"],
[data-testid="stToolbar"] svg, [data-testid="stMainMenu"] svg,
[data-testid="stHeader"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="collapsedControl"] [data-testid="stIconMaterial"],
[data-testid="collapsedControl"] svg { color: var(--text) !important; fill: var(--text) !important; }

/* Form-control glyphs: select chevrons, multiselect clear, number steppers */
div[data-baseweb="select"] svg, div[data-baseweb="select"] [data-baseweb="icon"] svg {
    fill: var(--input-text) !important; color: var(--input-text) !important;
}
.stNumberInput button { color: var(--input-text) !important; background: var(--input-bg) !important; border-color: var(--border) !important; }
.stNumberInput button:hover { background: var(--surface-2) !important; }
.stNumberInput button [data-testid="stIconMaterial"], .stNumberInput button svg { color: var(--input-text) !important; fill: var(--input-text) !important; }

/* Help "?" icons next to widget labels */
[data-testid="stWidgetLabelHelp"] svg, [data-testid="stTooltipHoverTarget"] svg { fill: var(--text-muted) !important; color: var(--text-muted) !important; }

/* Expander / popover trigger headers */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] { color: var(--text) !important; }

/* ============================ Dataframe ========================== */
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid var(--border); }

/* themed market table — a real HTML table (the canvas st.dataframe can't be
   recoloured by CSS, so the big browse table is rendered as HTML instead) */
.dse-table-wrap {
    max-height: 460px; overflow: auto; border: 1px solid var(--border);
    border-radius: 16px; background: var(--surface);
    box-shadow: 0 8px 30px var(--shadow-card);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
.dse-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.dse-table thead th {
    position: sticky; top: 0; z-index: 1;
    background: var(--surface-2); color: var(--text-muted);
    font-weight: 700; font-size: 0.70rem; letter-spacing: 0.05em; text-transform: uppercase;
    text-align: right; padding: 12px 16px; border-bottom: 1px solid var(--border); white-space: nowrap;
}
.dse-table thead th.l { text-align: left; }
.dse-table tbody td {
    padding: 10px 16px; color: var(--text); text-align: right; white-space: nowrap;
    border-bottom: 1px solid var(--border);
}
.dse-table tbody tr:last-child td { border-bottom: none; }
.dse-table tbody tr:hover td { background: var(--surface-2); }
.dse-table td.l { text-align: left; }
.dse-table .code { font-weight: 800; color: var(--text-strong); letter-spacing: 0.01em; }
.dse-table .sector { color: var(--text-muted); }
.dse-table .idx { color: var(--text-faint); }
.dse-table .up { color: #10b981; font-weight: 700; }
.dse-table .down { color: #ef4444; font-weight: 700; }
.dse-table .flat { color: var(--text-muted); font-weight: 700; }
.dse-table td.wrap { white-space: normal; min-width: 200px; color: var(--text-muted); }

/* ============================ Top toast ========================= */
@keyframes topToast {
    0%   { transform: translate(-50%, -160%); opacity: 0; }
    11%  { transform: translate(-50%, 0);     opacity: 1; }
    12%  { transform: translate(-50%, 4px);   opacity: 1; }
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
.error-banner { background: linear-gradient(135deg, rgba(248,113,113,0.20), rgba(248,113,113,0.07)); border: 1px solid rgba(248,113,113,0.5); border-radius: 16px; padding: 0.9rem 1.2rem; color: #ef4444; font-weight: 600; margin-bottom: 1rem; }
.muted { color: var(--text-muted); font-size: 0.82rem; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.detail-cell { background: var(--surface-inset); border: 1px solid var(--border); border-radius: 13px; padding: 0.7rem 0.85rem; }
.detail-cell .k { font-size: 0.66rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.07em; }
.detail-cell .v { font-size: 1.12rem; font-weight: 700; color: var(--text-strong); margin-top: 3px; font-variant-numeric: tabular-nums; }
"""


def _root_vars(theme: str) -> str:
    palette = _PALETTES.get(theme, _PALETTES["dark"])
    body = "".join(f"  --{key}: {value};\n" for key, value in palette.items())
    return ":root {\n" + body + "}\n"


def inject(theme: str = "dark") -> None:
    """Inject the global premium theme for the chosen ``theme`` (dark|light)."""
    st.markdown("<style>\n" + _root_vars(theme) + _BASE_CSS + "\n</style>",
                unsafe_allow_html=True)
