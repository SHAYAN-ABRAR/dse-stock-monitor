"""
app.py
------
DSE Stock Monitor — premium Streamlit dashboard.

Run with:
    streamlit run app.py

The heavy lifting (scraping, AI, alerts, logging) happens in a background
thread owned by `StockMonitor` (scheduler.py). This file is purely the
presentation + control layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from config import AppConfig, load_config
from scheduler import StockMonitor
from utils import (fmt_hhmm_12, fmt_ts, is_trading_hours,
                   is_valid_whatsapp_number, normalize_whatsapp_number,
                   now_dhaka, parse_hhmm, setup_logging)

# ======================================================================
# Page setup
# ======================================================================
st.set_page_config(
    page_title="DSE Stock Monitor — OLYMPIC",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup_logging()

GLASS_CSS = """
<style>
/* ---------- global backdrop: deep navy gradient ---------- */
.stApp {
    background: radial-gradient(1200px 600px at 15% 0%, #1e3a5f 0%, transparent 60%),
                radial-gradient(1000px 500px at 85% 10%, #3b1d5e 0%, transparent 55%),
                linear-gradient(160deg, #0b1220 0%, #0e1729 45%, #101a30 100%);
    color: #e8eefc;
}
header[data-testid="stHeader"] { background: transparent; }

/* ---------- glass cards ---------- */
.glass-card {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    padding: 1.1rem 1.3rem;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    margin-bottom: 0.6rem;
    min-height: 118px;
}
.glass-card .kpi-label {
    font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase;
    color: #9fb3d9; margin-bottom: 0.35rem;
}
.glass-card .kpi-value {
    font-size: 1.85rem; font-weight: 700; color: #ffffff; line-height: 1.15;
}
.glass-card .kpi-sub { font-size: 0.8rem; color: #8ea4cc; margin-top: 0.3rem; }

/* accent variants */
.kpi-accent-green  .kpi-value { color: #4ade80; }
.kpi-accent-red    .kpi-value { color: #f87171; }
.kpi-accent-amber  .kpi-value { color: #fbbf24; }
.kpi-accent-blue   .kpi-value { color: #60a5fa; }
.kpi-accent-violet .kpi-value { color: #c084fc; }

/* ---------- hero header ---------- */
.hero {
    background: linear-gradient(135deg, rgba(96,165,250,0.18), rgba(192,132,252,0.14));
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 22px;
    padding: 1.4rem 1.8rem;
    backdrop-filter: blur(16px);
    margin-bottom: 1.2rem;
}
.hero h1 { margin: 0; font-size: 1.7rem; color: #fff; }
.hero p  { margin: 0.3rem 0 0 0; color: #9fb3d9; font-size: 0.92rem; }

/* ---------- status pills ---------- */
.pill {
    display: inline-block; padding: 0.28rem 0.85rem; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; letter-spacing: 0.03em;
}
.pill-green { background: rgba(74,222,128,0.15); color:#4ade80; border:1px solid rgba(74,222,128,0.4); }
.pill-red   { background: rgba(248,113,113,0.15); color:#f87171; border:1px solid rgba(248,113,113,0.4); }
.pill-amber { background: rgba(251,191,36,0.15); color:#fbbf24; border:1px solid rgba(251,191,36,0.4); }
.pill-blue  { background: rgba(96,165,250,0.15); color:#60a5fa; border:1px solid rgba(96,165,250,0.4); }

/* ---------- section titles ---------- */
.section-title {
    font-size: 1.05rem; font-weight: 700; color: #dbe7ff;
    margin: 1.1rem 0 0.5rem 0; letter-spacing: 0.02em;
}

/* ---------- buttons ---------- */
div.stButton > button {
    border-radius: 12px; font-weight: 700; border: 1px solid rgba(255,255,255,0.18);
    backdrop-filter: blur(8px); padding: 0.55rem 1rem; width: 100%;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; border: none;
}
/* emergency collect-now button — high-visibility amber/red gradient */
.st-key-btn_emergency button {
    background: linear-gradient(135deg, #f59e0b, #dc2626) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    font-weight: 800 !important;
    letter-spacing: 0.03em;
    box-shadow: 0 0 16px rgba(220,38,38,0.40);
}
.st-key-btn_emergency button:hover {
    filter: brightness(1.15);
    box-shadow: 0 0 24px rgba(220,38,38,0.65);
}
/* grayed-out (unclickable) state */
div.stButton > button:disabled {
    background: rgba(255,255,255,0.07) !important;
    color: #64748b !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    cursor: not-allowed;
    box-shadow: none !important;
}

/* ---------- pulsing red LIVE badge ---------- */
.live-badge {
    display: inline-flex; align-items: center; gap: 0.55rem;
    background: linear-gradient(135deg, #ef4444, #b91c1c);
    color: #ffffff; font-weight: 800; font-size: 0.95rem;
    letter-spacing: 0.18em;
    padding: 0.6rem 1.5rem; border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.25);
    animation: livePulse 1.6s ease-in-out infinite;
}
.live-badge .dot {
    width: 11px; height: 11px; border-radius: 50%;
    background: #ffffff;
    animation: dotBlink 1.6s ease-in-out infinite;
}
@keyframes livePulse {
    0%, 100% { box-shadow: 0 0 8px  rgba(239,68,68,0.45); }
    50%      { box-shadow: 0 0 28px rgba(239,68,68,0.95); }
}
@keyframes dotBlink {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.2; }
}

/* hide Streamlit's "Press Enter to submit/apply" hints inside inputs */
[data-testid="InputInstructions"] { display: none !important; }

/* ---------- error banner ---------- */
.error-banner {
    background: linear-gradient(135deg, rgba(248,113,113,0.20), rgba(248,113,113,0.08));
    border: 1px solid rgba(248,113,113,0.55);
    border-radius: 16px; padding: 1rem 1.3rem; color: #fecaca;
    font-weight: 600; margin-bottom: 1rem;
}

/* ---------- dataframes / sidebar ---------- */
[data-testid="stSidebar"] {
    background: rgba(10, 16, 30, 0.85);
    border-right: 1px solid rgba(255,255,255,0.08);
    backdrop-filter: blur(18px);
}
[data-testid="stSidebar"] * { color: #dbe7ff; }
</style>
"""
st.markdown(GLASS_CSS, unsafe_allow_html=True)


# ======================================================================
# Singletons — survive Streamlit reruns; one per server process
# ======================================================================
# Bump this whenever AppConfig or StockMonitor gains/loses fields. It is
# part of the cache key, so a code update on a live server rebuilds the
# monitor instead of serving a stale object (-> AttributeError).
CONFIG_SCHEMA_VERSION = 9


@st.cache_resource(show_spinner=False)
def get_monitor(schema_version: int) -> StockMonitor:
    cfg = load_config()
    return StockMonitor(cfg)


monitor = get_monitor(CONFIG_SCHEMA_VERSION)
cfg: AppConfig = monitor.cfg

# Self-heal: if a cached monitor from an older code version is still
# missing current fields, drop the cache and rebuild once.
if not hasattr(cfg, "trading_continuous_end"):
    get_monitor.clear()
    monitor = get_monitor(CONFIG_SCHEMA_VERSION)
    cfg = monitor.cfg


# ======================================================================
# Small render helpers
# ======================================================================
def kpi_card(label: str, value: str, sub: str = "", accent: str = "") -> str:
    return (
        f'<div class="glass-card {accent}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


def pill(text: str, kind: str) -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


def render_price_chart(df: pd.DataFrame) -> None:
    """Plotly line chart of the recent price trend with the target band."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["ltp"], mode="lines+markers", name="LTP",
        line=dict(color="#60a5fa", width=2.5),
        marker=dict(size=6, color="#93c5fd"),
        fill="tozeroy", fillcolor="rgba(96,165,250,0.07)",
    ))
    # Target range band
    fig.add_hrect(
        y0=cfg.target_min_price, y1=cfg.target_max_price,
        fillcolor="rgba(74,222,128,0.12)", line_width=0,
        annotation_text="Target range", annotation_font_color="#4ade80",
    )
    ymin = min(df["ltp"].min(), cfg.target_min_price) * 0.995
    ymax = max(df["ltp"].max(), cfg.target_max_price) * 1.005
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9fb3d9"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", title=None),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="LTP (BDT)",
                   range=[ymin, ymax]),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ======================================================================
# Sidebar — configuration & controls
# ======================================================================
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    st.markdown("**Target Price Range (BDT)**")
    col_lo, col_hi = st.columns(2)
    new_min = col_lo.number_input("Min", value=float(cfg.target_min_price),
                                  step=0.5, format="%.2f", key="tmin")
    new_max = col_hi.number_input("Max", value=float(cfg.target_max_price),
                                  step=0.5, format="%.2f", key="tmax")
    if (new_min, new_max) != (cfg.target_min_price, cfg.target_max_price):
        monitor.update_target_range(float(new_min), float(new_max))
        st.success(f"Range updated: {new_min:g} – {new_max:g}")

    st.divider()
    st.markdown("**Stock**")
    st.code(cfg.trading_code)

    interval_min = st.number_input(
        "Collect data every (minutes)",
        min_value=1, max_value=60, step=1,
        value=max(1, cfg.polling_interval_seconds // 60),
        help="How often the price is scraped during trading hours. "
             "Changes apply from the next collection. Minimum 1 minute "
             "to stay gentle on dsebd.org.",
        key="poll_interval_min",
    )
    if int(interval_min) != cfg.polling_interval_seconds // 60:
        monitor.update_polling_interval(int(interval_min))
        st.success(f"Data will be collected every {int(interval_min)} min "
                   f"(from the next collection)")

    st.markdown("**Trading Hours (Asia/Dhaka)**")
    st.code(
        f"Sun–Thu\n"
        f"Continuous : {fmt_hhmm_12(cfg.trading_start)} – {fmt_hhmm_12(cfg.trading_continuous_end)}\n"
        f"Post-close : {fmt_hhmm_12(cfg.trading_continuous_end)} – {fmt_hhmm_12(cfg.trading_end)}"
    )

    st.markdown("**WhatsApp (Twilio)**")

    # Read-only display of where alerts currently go. The number itself
    # is changed inside the credentials panel below.
    recipient_now = normalize_whatsapp_number(cfg.recipient_whatsapp_number)
    st.code(f"Alerts go to: {recipient_now or 'Not set'}")

    # --- Full Twilio credentials, editable in the site -----------------
    # Click to expand; changes apply immediately and are remembered
    # across restarts (saved to user_settings.json, which is gitignored).
    with st.expander("🔐 Twilio Credentials — click to view / change"):
        if cfg.twilio_configured:
            st.success("All credentials are saved on this device — "
                       "nothing to re-enter. The grey text in each box "
                       "shows the saved value.", icon="💾")
        st.caption("These credentials send the WhatsApp alerts. Get them "
                   "from [console.twilio.com](https://console.twilio.com). "
                   "Changes apply instantly — no restart needed. "
                   "**Leave a field empty to keep its saved value** — "
                   "only type in a box to change that one setting.")

        # Placeholders show the current value (token masked) so the
        # fields start EMPTY — the client types only what they want
        # to change, no backspacing needed.
        sid_now = cfg.twilio_account_sid.strip()
        sid_ph = (f"Current: {sid_now[:6]}…{sid_now[-4:]}"
                  if cfg.twilio_configured else "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        token_ph = ("Current token saved (hidden)"
                    if cfg.twilio_configured else "Paste your Auth Token")
        sender_now = normalize_whatsapp_number(cfg.twilio_whatsapp_number)
        recipient_now_ph = recipient_now or "+8801XXXXXXXXX"

        with st.form("twilio_creds_form", border=False, enter_to_submit=False):
            sid_in = st.text_input(
                "Account SID", value="", placeholder=sid_ph,
                help="Starts with 'AC' followed by 32 characters.")
            token_in = st.text_input(
                "Auth Token", value="", type="password", placeholder=token_ph,
                help="Hidden for security. Paste the token from the Twilio console.")
            sender_in = st.text_input(
                "Twilio WhatsApp sender number", value="",
                placeholder=sender_now or "+14155238886",
                help="The number Twilio sends FROM. Sandbox default: +14155238886")
            recipient_in = st.text_input(
                "Send alerts to this WhatsApp number", value="",
                placeholder=recipient_now_ph,
                help="The number that RECEIVES the alerts. International "
                     "format, e.g. +8801712345678. On the Twilio sandbox, a "
                     "new number must first send the 'join <code>' message "
                     "to the sandbox number before it can receive alerts.")
            save_creds = st.form_submit_button(
                "💾 Save credentials", type="primary", use_container_width=True)

        if save_creds:
            # Empty field -> keep the currently configured value.
            sid_clean = sid_in.strip() or sid_now
            token_clean = token_in.strip() or cfg.twilio_auth_token.strip()
            sender_clean = normalize_whatsapp_number(sender_in) or sender_now
            recipient_clean = (normalize_whatsapp_number(recipient_in)
                               or recipient_now)
            problems = []
            if not re.fullmatch(r"AC[0-9a-fA-F]{32}", sid_clean):
                problems.append("Account SID must be 'AC' + 32 characters "
                                "(copied exactly from the Twilio console).")
            if len(token_clean) < 16 or "your_auth_token" in token_clean.lower():
                problems.append("Auth Token looks invalid — paste the real "
                                "token, not the placeholder.")
            if not is_valid_whatsapp_number(sender_clean):
                problems.append("Sender number must be international format, "
                                "e.g. +14155238886.")
            if not is_valid_whatsapp_number(recipient_clean):
                problems.append("Recipient number must be international "
                                "format, e.g. +8801712345678.")
            if problems:
                for p in problems:
                    st.error(p)
            else:
                monitor.update_twilio_credentials(
                    sid_clean, token_clean, sender_clean)
                ready = monitor.update_recipient_number(recipient_clean)
                st.toast(f"Saved — alerts go to {recipient_clean}"
                         + ("" if ready else " (check credentials)"),
                         icon="✅" if ready else "⚠️")
                st.rerun()  # refresh the 'Alerts go to' display above

    if monitor.notifier.ready:
        st.success("Twilio configured", icon="✅")
        if st.button("Send test WhatsApp message"):
            res = monitor.notifier.send(
                f"✅ Test message from DSE Monitor — {now_dhaka(cfg):%Y-%m-%d %I:%M:%S %p}"
            )
            if res.sent:
                st.success(f"Sent! SID: {res.sid}")
            else:
                st.error(f"Failed: {res.error}")
    else:
        st.warning("Twilio not configured — alerts disabled. Open "
                   "**🔐 Twilio Credentials** above and enter your real "
                   "Account SID, Auth Token and sender number.", icon="⚠️")


# ======================================================================
# Live clock — ticks every second client-side (no app reruns needed),
# with a countdown to the next market open / close underneath.
# ======================================================================
_CLOCK_HTML = """
<div style="
    display:flex; flex-direction:column; align-items:center; gap:3px;
    font-family:'Segoe UI', system-ui, sans-serif;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px; padding: 10px 18px;
    backdrop-filter: blur(14px);">
    <div style="display:flex; align-items:center; gap:14px;">
        <span id="liveclock" style="
            font-size: 1.9rem; font-weight: 800; letter-spacing: 0.08em;
            color: #ffffff; font-variant-numeric: tabular-nums;">--:--:--</span>
        <span id="livedate" style="font-size:0.85rem; color:#9fb3d9;"></span>
    </div>
    <span id="countdown" style="font-size:0.78rem; color:#8ea4cc;
          letter-spacing:0.04em; font-variant-numeric: tabular-nums;"></span>
</div>
<script>
    // Injected from the Python config:
    const TZ = "__TZ__";
    const TRADING_DAYS = [__DAYS__];   // JS getDay(): Sun=0 ... Sat=6
    const START_MIN = __START_MIN__;   // market open, minutes after midnight
    const END_MIN = __END_MIN__;       // market close incl. post-close session

    function dhakaNow() {
        return new Date(new Date().toLocaleString("en-US", { timeZone: TZ }));
    }
    function fmtDur(ms) {
        let s = Math.max(0, Math.floor(ms / 1000));
        const d = Math.floor(s / 86400); s -= d * 86400;
        const h = Math.floor(s / 3600); s -= h * 3600;
        const m = Math.floor(s / 60);   s -= m * 60;
        const core = [h, m, s].map(x => String(x).padStart(2, "0")).join(":");
        return d > 0 ? d + "d " + core : core;
    }
    function countdownText() {
        const now = dhakaNow();
        const mins = now.getHours() * 60 + now.getMinutes();
        if (TRADING_DAYS.includes(now.getDay()) && mins >= START_MIN && mins < END_MIN) {
            const end = new Date(now);
            end.setHours(Math.floor(END_MIN / 60), END_MIN % 60, 0, 0);
            return "\\uD83D\\uDFE2 Market closes in " + fmtDur(end - now);
        }
        // Closed: find the next trading day's opening bell.
        for (let d = 0; d < 8; d++) {
            const cand = new Date(now);
            cand.setDate(now.getDate() + d);
            cand.setHours(Math.floor(START_MIN / 60), START_MIN % 60, 0, 0);
            if (TRADING_DAYS.includes(cand.getDay()) && cand > now) {
                return "\\u23F3 Market opens in " + fmtDur(cand - now);
            }
        }
        return "";
    }
    function tick() {
        const now = new Date();
        document.getElementById("liveclock").textContent =
            now.toLocaleTimeString("en-US", { timeZone: TZ, hour12: true,
                hour: "2-digit", minute: "2-digit", second: "2-digit" });
        document.getElementById("livedate").textContent =
            now.toLocaleDateString("en-US", { timeZone: TZ,
                weekday: "long", year: "numeric", month: "short", day: "numeric" })
            + " \\u00B7 Dhaka (BDT)";
        document.getElementById("countdown").textContent = countdownText();
    }
    tick();
    setInterval(tick, 1000);
</script>
"""

_start_t = parse_hhmm(cfg.trading_start)
_end_t = parse_hhmm(cfg.trading_end)
components.html(
    _CLOCK_HTML
    .replace("__TZ__", cfg.timezone)
    # Python weekday (Mon=0..Sun=6) -> JS getDay() (Sun=0..Sat=6)
    .replace("__DAYS__", ",".join(str((d + 1) % 7) for d in sorted(cfg.trading_days)))
    .replace("__START_MIN__", str(_start_t.hour * 60 + _start_t.minute))
    .replace("__END_MIN__", str(_end_t.hour * 60 + _end_t.minute)),
    height=102,
)

# ======================================================================
# Hero header + Start/Stop controls
# ======================================================================
st.markdown(
    f"""
    <div class="hero">
        <h1>📈 DSE Stock Monitor — {cfg.trading_code}</h1>
        <p>Dhaka Stock Exchange · live LTP tracking · WhatsApp alerts ·
           AI anomaly detection · target {cfg.target_min_price:g}–{cfg.target_max_price:g} BDT</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ======================================================================
# Live dashboard — auto-refreshes every 10 s without a full page reload
# ======================================================================
@st.fragment(run_every="10s")
def live_dashboard() -> None:
    snap: Dict[str, Any] = monitor.snapshot()
    running: bool = snap["running"]
    open_now, hours_reason = is_trading_hours(cfg)

    # ---- Start / Stop / Emergency controls + LIVE badge ----------------
    # While running:  Start is grayed out & unclickable, Stop gets the
    # colorful gradient, and a pulsing red LIVE badge appears.
    # The emergency button is ALWAYS clickable — it collects data
    # instantly without waiting for the next scheduled poll.
    ctrl1, ctrl2, ctrl3, badge_col, _sp = st.columns(
        [1.2, 1.2, 1.4, 1.1, 1.1], vertical_alignment="center"
    )
    with ctrl1:
        if st.button("▶ Start Tracking",
                     type="secondary" if running else "primary",
                     disabled=running,
                     use_container_width=True, key="btn_start"):
            monitor.start()
            st.toast("Monitoring started", icon="🟢")
            st.rerun()
    with ctrl2:
        if st.button("⏸ Stop Tracking",
                     type="primary" if running else "secondary",
                     disabled=not running,
                     use_container_width=True, key="btn_stop"):
            monitor.stop()
            st.toast("Monitoring stopped", icon="🔴")
            st.rerun()
    with ctrl3:
        if st.button("⚡ Collect Data Now",
                     use_container_width=True, key="btn_emergency",
                     help="Emergency collection: scrape the price right now "
                          "instead of waiting for the next scheduled poll. "
                          "Alerts fire immediately if the price is in range."):
            with st.spinner("Collecting data now…"):
                fresh = monitor.poll_now()
            if fresh["last_scrape_success"]:
                st.toast(f"Collected! LTP = {fresh['last_price']}", icon="⚡")
            else:
                st.toast(f"Collection failed: {fresh['last_error']}", icon="❌")
            st.rerun()
    with badge_col:
        if running:
            st.markdown(
                '<div class="live-badge"><span class="dot"></span>LIVE</div>',
                unsafe_allow_html=True,
            )

    # ---- prominent error banner -------------------------------------
    if snap["paused_due_to_errors"]:
        st.markdown(
            f'<div class="error-banner">🚨 MONITORING AUTO-PAUSED — scraping failed '
            f'{cfg.max_consecutive_failures} consecutive times.<br>'
            f'Last error: {snap["last_error"]}<br>'
            f'Press <b>Start Tracking</b> to resume.</div>',
            unsafe_allow_html=True,
        )
    elif snap["last_error"] and not snap["last_scrape_success"]:
        st.markdown(
            f'<div class="error-banner">⚠️ Last scrape failed '
            f'({snap["consecutive_errors"]}/{cfg.max_consecutive_failures}): '
            f'{snap["last_error"]}</div>',
            unsafe_allow_html=True,
        )

    # ---- status pills row --------------------------------------------
    if snap["running"]:
        run_pill = pill("● RUNNING", "green")
    elif snap["paused_due_to_errors"]:
        run_pill = pill("● PAUSED (errors)", "red")
    else:
        run_pill = pill("● STOPPED", "red")
    hours_pill = pill("MARKET OPEN", "green") if open_now else pill("MARKET CLOSED", "amber")
    # Next scheduled data collection — so the client always knows when
    # the next automatic scrape will happen.
    next_pill = ""
    next_caption = ""
    if running:
        if snap["next_poll_at"]:
            next_time = snap["next_poll_at"].strftime("%I:%M:%S %p").lstrip("0")
            next_pill = pill(f"⏱ NEXT COLLECTION · {next_time}", "blue")
            next_caption = f" · Next data collection time: {next_time}"
        else:
            next_pill = pill("⏱ WAITING FOR MARKET OPEN", "amber")
            next_caption = " · Next data collection: when the market opens"

    st.markdown(
        f'{run_pill}&nbsp;&nbsp;{hours_pill}&nbsp;&nbsp;{next_pill}',
        unsafe_allow_html=True,
    )
    st.caption(hours_reason + next_caption)

    # ---- KPI cards row 1 ----------------------------------------------
    price = snap["last_price"]
    in_range = (price is not None
                and cfg.target_min_price <= price <= cfg.target_max_price)
    price_accent = "kpi-accent-green" if in_range else "kpi-accent-blue"

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Current Price (LTP)",
                         f"{price:.2f} ৳" if price is not None else "—",
                         "IN TARGET RANGE 🎯" if in_range else f"{cfg.trading_code} · DSE",
                         price_accent), unsafe_allow_html=True)
    c2.markdown(kpi_card("Target Range",
                         f"{cfg.target_min_price:g} – {cfg.target_max_price:g}",
                         "Alert when LTP enters this band",
                         "kpi-accent-violet"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Monitoring",
                         "ACTIVE" if snap["running"] else "STOPPED",
                         f"Last scrape: {fmt_ts(snap['last_scrape_time'])}",
                         "kpi-accent-green" if snap["running"] else "kpi-accent-red"),
                unsafe_allow_html=True)
    c4.markdown(kpi_card("Trading Hours",
                         "OPEN" if open_now else "CLOSED",
                         f"Sun–Thu · {fmt_hhmm_12(cfg.trading_start)}–{fmt_hhmm_12(cfg.trading_continuous_end)}"
                         f" · post-close till {fmt_hhmm_12(cfg.trading_end)}",
                         "kpi-accent-green" if open_now else "kpi-accent-amber"),
                unsafe_allow_html=True)

    # ---- KPI cards row 2 ----------------------------------------------
    stats = monitor.db.stats()
    err_accent = ("kpi-accent-red" if snap["consecutive_errors"] > 0
                  else "kpi-accent-green")
    ai = snap["ai_last_result"]
    ai_value = "—"
    ai_sub = "AI disabled" if not cfg.ai_enabled else "Collecting data…"
    ai_accent = "kpi-accent-blue"
    if cfg.ai_enabled and ai is not None:
        ai_value = "ANOMALY" if ai.is_anomaly else "NORMAL"
        ai_accent = "kpi-accent-red" if ai.is_anomaly else "kpi-accent-green"
        ai_sub = f"{ai.note} · Δ{ai.pct_change:+.2f}% · n={ai.samples}"

    d1, d2, d3, d4 = st.columns(4)
    d1.markdown(kpi_card("Alerts Sent", str(stats["alerts_sent"]),
                         snap["last_alert_status"], "kpi-accent-amber"),
                unsafe_allow_html=True)
    d2.markdown(kpi_card("Consecutive Errors",
                         str(snap["consecutive_errors"]),
                         f"Auto-pause at {cfg.max_consecutive_failures}",
                         err_accent), unsafe_allow_html=True)
    d3.markdown(kpi_card("AI Analysis", ai_value, ai_sub, ai_accent),
                unsafe_allow_html=True)
    d4.markdown(kpi_card("Total Scrapes", str(stats["total_scrapes"]),
                         f"{stats['successful_scrapes']} successful",
                         "kpi-accent-blue"), unsafe_allow_html=True)

    # ---- chart + alert history ----------------------------------------
    st.markdown('<div class="section-title">📊 Recent Price Trend</div>',
                unsafe_allow_html=True)
    scrapes = monitor.db.recent_scrapes(limit=200)
    chart_df = scrapes[scrapes["success"] == 1].iloc[::-1].copy()  # chronological
    if not chart_df.empty:
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
        render_price_chart(chart_df)
    else:
        st.info("No price data yet. Press **Start Tracking** to begin, or "
                "**⚡ Collect Data Now** for an instant collection (works "
                "even while the market is closed).")

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section-title">🔔 Alert History</div>',
                    unsafe_allow_html=True)
        alerts = monitor.db.recent_alerts(limit=25)
        if alerts.empty:
            st.caption("No alerts sent yet.")
        else:
            alerts = alerts.copy()
            alerts["timestamp"] = pd.to_datetime(
                alerts["timestamp"]).dt.strftime("%Y-%m-%d %I:%M:%S %p")
            alerts = alerts.rename(columns={
                "timestamp": "Time", "alert_type": "Type",
                "price": "LTP", "message": "Message", "sent": "Sent"})
            st.dataframe(alerts, use_container_width=True, height=300,
                         hide_index=True)
    with right:
        st.markdown('<div class="section-title">🗂 Historical Price Log</div>',
                    unsafe_allow_html=True)
        if scrapes.empty:
            st.caption("No scrapes logged yet.")
        else:
            log_df = scrapes.copy()
            log_df["timestamp"] = pd.to_datetime(
                log_df["timestamp"]).dt.strftime("%Y-%m-%d %I:%M:%S %p")
            log_df = log_df.rename(columns={
                "timestamp": "Time", "ltp": "LTP", "success": "OK",
                "alert_sent": "Alert", "ai_status": "AI Status",
                "error": "Error"})
            st.dataframe(log_df.head(50), use_container_width=True,
                         height=300, hide_index=True)

    st.caption(
        f"Dashboard refreshed {now_dhaka(cfg):%Y-%m-%d %I:%M:%S %p} (Asia/Dhaka) · "
        f"polling every {cfg.polling_interval_seconds // 60} min · "
        f"data: dsebd.org"
    )


live_dashboard()
