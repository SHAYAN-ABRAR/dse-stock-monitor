"""
runtime.py
----------
Shared runtime helpers used by every view: the cached ``MarketMonitor``
singleton, global theme injection, the JS live clock, the sidebar control
panel, and small HTML render helpers.

The monitor is created once per Streamlit server process via
``st.cache_resource`` and survives page navigation + reruns, so its
background thread (and in-memory market cache) is shared across all views.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from components import charts, styles
from config import AppConfig, load_config
from market_monitor import MarketMonitor
from utils import (fmt_hhmm_12, fmt_ts, is_trading_hours, now_dhaka,
                   parse_hhmm)

# Available UI themes and the default used before a choice is persisted.
THEMES = ("dark", "light")
THEME_DEFAULT = "dark"

# Bump when MarketMonitor / AppConfig gain or lose fields so a live server
# rebuilds the cached singleton instead of serving a stale object.
SCHEMA_VERSION = 4


@st.cache_resource(show_spinner=False)
def _build_monitor(schema_version: int) -> MarketMonitor:
    return MarketMonitor(load_config())


def get_monitor() -> MarketMonitor:
    """Return the process-wide MarketMonitor (self-healing across upgrades)."""
    monitor = _build_monitor(SCHEMA_VERSION)
    # Rebuild if a hot-reload left us holding a monitor from an older code
    # version (missing a cfg field or a newly added method).
    if (not hasattr(monitor.cfg, "refresh_interval_seconds")
            or not hasattr(monitor, "condition_hits")):
        _build_monitor.clear()
        monitor = _build_monitor(SCHEMA_VERSION)
    return monitor


# ----------------------------------------------------------------------
# Small HTML render helpers
# ----------------------------------------------------------------------
def inject_theme(theme: str = THEME_DEFAULT) -> None:
    theme = theme if theme in THEMES else THEME_DEFAULT
    styles.inject(theme)
    charts.apply_theme(theme)


# ----------------------------------------------------------------------
# Theme preference (dark / light) — persisted per deployment in app_state
# and cached in session_state for instant toggling.
# ----------------------------------------------------------------------
def get_theme(monitor: MarketMonitor) -> str:
    """Return the active UI theme, seeding session_state from the DB once."""
    if "ui_theme" not in st.session_state:
        try:
            stored = monitor.repo.get_state("ui_theme", THEME_DEFAULT)
        except Exception:
            stored = THEME_DEFAULT
        st.session_state["ui_theme"] = stored if stored in THEMES else THEME_DEFAULT
    theme = st.session_state.get("ui_theme", THEME_DEFAULT)
    return theme if theme in THEMES else THEME_DEFAULT


def set_theme(monitor: MarketMonitor, theme: str) -> None:
    theme = theme if theme in THEMES else THEME_DEFAULT
    st.session_state["ui_theme"] = theme
    try:
        monitor.repo.set_state("ui_theme", theme)
    except Exception:
        pass


def pill(text: str, kind: str) -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


def kpi_card(label: str, value: str, sub: str = "", accent: str = "") -> str:
    return (
        f'<div class="glass-card {accent}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# Top toast — slides down from the top, holds ~1.5s, slides back up.
# Queue a message with flash(); render_flash() (called once per run from
# app.py) shows it. A counter forces the DOM node to be recreated so the
# CSS animation replays every time, even for an identical message.
# ----------------------------------------------------------------------
def flash(message: str, icon: str = "✅") -> None:
    """Queue a top-toast notification. Multiple queued toasts play one
    after another (so deleting/adding several things shows several toasts)."""
    queue = st.session_state.get("_flash_queue", [])
    queue.append({"msg": message, "icon": icon})
    st.session_state["_flash_queue"] = queue


# Seconds between the start of consecutive toasts (≈ one toast's full life).
_TOAST_STAGGER = 1.9


def render_flash() -> None:
    queue = st.session_state.pop("_flash_queue", None)
    if not queue:
        return
    n0 = st.session_state.get("_flash_n", 0)
    st.session_state["_flash_n"] = n0 + len(queue)
    html = ""
    for i, item in enumerate(queue):
        # A staggered animation-delay makes each toast appear after the
        # previous one finishes — a clean sequential cascade, all rendered
        # in a single pass so none get cut short by a rerun.
        html += (
            f'<div class="top-toast" data-n="{n0 + i + 1}" '
            f'style="animation-delay:{i * _TOAST_STAGGER:.2f}s">'
            f'<span class="tt-ico">{item.get("icon", "")}</span>'
            f'{item.get("msg", "")}</div>'
        )
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Reusable confirmation modal (SweetAlert-style) for destructive actions
# ----------------------------------------------------------------------
def request_confirm(flag_key: str, value=True) -> None:
    """Flag a destructive action for confirmation, then rerun so the modal
    opens at the top level. The modal must be opened from a persistent flag
    (not directly on the button press) so its own buttons are processed on
    the rerun that handles the click."""
    st.session_state[flag_key] = value
    st.rerun()


@st.dialog("⚠️ Please confirm")
def confirm_action(message: str, detail: str = "", on_confirm=None,
                   clear_key: Optional[str] = None,
                   confirm_label: str = "✅ Yes, proceed",
                   success_message: str = "", success_icon: str = "🗑") -> None:
    """Open a modal asking the user to confirm before a destructive action.

    ``on_confirm`` runs only if the user clicks the confirm button.
    ``clear_key`` (if given) is popped from session_state on close so a
    flag-driven opener does not re-trigger the dialog. ``success_message``
    (if given) is flashed as a top toast after a confirmed action.
    """
    st.markdown(f"#### {message}")
    if detail:
        st.caption(detail)
    yes, no = st.columns(2)
    if yes.button(confirm_label, type="primary", width="stretch",
                  key="_confirm_yes"):
        try:
            if on_confirm is not None:
                on_confirm()
        finally:
            if clear_key:
                st.session_state.pop(clear_key, None)
        if success_message:
            flash(success_message, success_icon)
        st.rerun()
    if no.button("✖ Cancel", width="stretch", key="_confirm_no"):
        if clear_key:
            st.session_state.pop(clear_key, None)
        st.rerun()


# ----------------------------------------------------------------------
# Live clock (ticks client-side every second; counts down to open/close)
# ----------------------------------------------------------------------
# Per-theme colours for the clock iframe (it has its own document, so the
# page's CSS variables don't reach it — we substitute colours directly).
_CLOCK_COLORS = {
    "dark": dict(bg="rgba(255,255,255,0.05)", border="rgba(255,255,255,0.11)",
                 text="#ffffff", sub="#9fb3d9", count="#8ea4cc"),
    "light": dict(bg="rgba(255,255,255,0.75)", border="rgba(20,40,80,0.13)",
                  text="#0b1526", sub="#566b8c", count="#6a7da0"),
}

_CLOCK_HTML = """
<div style="display:flex;flex-direction:column;align-items:center;gap:3px;
    font-family:'Inter','Segoe UI',system-ui,sans-serif;
    background:__CLOCKBG__;border:1px solid __CLOCKBORDER__;
    border-radius:16px;padding:10px 18px;backdrop-filter:blur(14px);">
  <div style="display:flex;align-items:center;gap:14px;">
    <span id="liveclock" style="font-size:1.8rem;font-weight:800;letter-spacing:0.07em;
        color:__CLOCKTEXT__;font-variant-numeric:tabular-nums;">--:--:--</span>
    <span id="livedate" style="font-size:0.82rem;color:__CLOCKSUB__;"></span>
  </div>
  <span id="countdown" style="font-size:0.76rem;color:__CLOCKCOUNT__;letter-spacing:0.04em;
        font-variant-numeric:tabular-nums;"></span>
</div>
<script>
  const TZ = "__TZ__";
  const TRADING_DAYS = [__DAYS__];
  const START_MIN = __START_MIN__, END_MIN = __END_MIN__;
  function dhakaNow(){ return new Date(new Date().toLocaleString("en-US",{timeZone:TZ})); }
  function fmtDur(ms){ let s=Math.max(0,Math.floor(ms/1000));
    const d=Math.floor(s/86400);s-=d*86400;const h=Math.floor(s/3600);s-=h*3600;
    const m=Math.floor(s/60);s-=m*60;
    const core=[h,m,s].map(x=>String(x).padStart(2,"0")).join(":");
    return d>0?d+"d "+core:core; }
  function countdownText(){
    const now=dhakaNow();const mins=now.getHours()*60+now.getMinutes();
    if(TRADING_DAYS.includes(now.getDay())&&mins>=START_MIN&&mins<END_MIN){
      const end=new Date(now);end.setHours(Math.floor(END_MIN/60),END_MIN%60,0,0);
      return "\\uD83D\\uDFE2 Market closes in "+fmtDur(end-now);
    }
    for(let d=0;d<8;d++){const c=new Date(now);c.setDate(now.getDate()+d);
      c.setHours(Math.floor(START_MIN/60),START_MIN%60,0,0);
      if(TRADING_DAYS.includes(c.getDay())&&c>now) return "\\u23F3 Market opens in "+fmtDur(c-now);}
    return "";
  }
  function tick(){const now=new Date();
    document.getElementById("liveclock").textContent=
      now.toLocaleTimeString("en-US",{timeZone:TZ,hour12:true,hour:"2-digit",minute:"2-digit",second:"2-digit"});
    document.getElementById("livedate").textContent=
      now.toLocaleDateString("en-US",{timeZone:TZ,weekday:"long",year:"numeric",month:"short",day:"numeric"})+" \\u00B7 Dhaka (BDT)";
    document.getElementById("countdown").textContent=countdownText();
  }
  tick();setInterval(tick,1000);
</script>
"""


def live_clock(cfg: AppConfig) -> None:
    start_t = parse_hhmm(cfg.trading_start)
    end_t = parse_hhmm(cfg.trading_end)
    theme = st.session_state.get("ui_theme", THEME_DEFAULT)
    colors = _CLOCK_COLORS.get(theme, _CLOCK_COLORS["dark"])
    st.iframe(
        _CLOCK_HTML
        .replace("__TZ__", cfg.timezone)
        .replace("__DAYS__", ",".join(str((d + 1) % 7) for d in sorted(cfg.trading_days)))
        .replace("__START_MIN__", str(start_t.hour * 60 + start_t.minute))
        .replace("__END_MIN__", str(end_t.hour * 60 + end_t.minute))
        .replace("__CLOCKBG__", colors["bg"])
        .replace("__CLOCKBORDER__", colors["border"])
        .replace("__CLOCKTEXT__", colors["text"])
        .replace("__CLOCKSUB__", colors["sub"])
        .replace("__CLOCKCOUNT__", colors["count"]),
        height=100,
    )


# ----------------------------------------------------------------------
# Shared sidebar control panel (rendered once from app.py, under the nav)
# ----------------------------------------------------------------------
def render_sidebar(monitor: MarketMonitor) -> None:
    cfg = monitor.cfg
    snap = monitor.snapshot()
    with st.sidebar:
        # The separating line above the brand is drawn as a CSS top-border on
        # .sb-brand (light mode only) — no extra element, so no extra gap.
        st.markdown('<div class="sb-brand">📈 DSE Terminal</div>',
                    unsafe_allow_html=True)
        st.caption("Dhaka Stock Exchange · live monitoring platform")

        # ---- Appearance: sun / moon sliding toggle switch ----
        cur_theme = get_theme(monitor)
        nxt_theme = "light" if cur_theme == "dark" else "dark"
        mode_label = "🌙 Dark mode" if cur_theme == "dark" else "☀️ Light mode"
        lab_col, sw_col = st.columns([1.5, 1])
        lab_col.markdown(f'<div class="theme-label">{mode_label}</div>',
                         unsafe_allow_html=True)
        with sw_col:
            # A fully-styled button acting as a switch; the knob side + icons
            # are driven by CSS keyed on the theme in the button's key.
            if st.button("Toggle theme", key=f"theme_toggle_{cur_theme}",
                         help=f"Switch to {nxt_theme} mode"):
                set_theme(monitor, nxt_theme)
                st.rerun()

        st.divider()

        # ---- Live monitoring controls ----
        running = snap["running"]
        st.markdown("**Live monitoring**")
        c1, c2 = st.columns(2)
        if c1.button("▶ Start", type="primary" if not running else "secondary",
                     disabled=running, width="stretch", key="sb_start"):
            monitor.start()
            flash("Monitoring started", "🟢")
            st.rerun()
        if c2.button("⏸ Stop", type="primary" if running else "secondary",
                     disabled=not running, width="stretch", key="sb_stop"):
            monitor.stop()
            flash("Monitoring stopped", "🔴")
            st.rerun()

        status = (pill("● LIVE", "green") if running
                  else pill("● PAUSED", "red"))
        open_now, reason = is_trading_hours(cfg)
        mkt = pill("MARKET OPEN", "green") if open_now else pill("MARKET CLOSED", "amber")
        st.markdown(f"{status}&nbsp;&nbsp;{mkt}", unsafe_allow_html=True)
        st.caption(reason)

        st.divider()
        # ---- Refresh cadence ----
        st.markdown("**Data refresh**")
        interval = st.number_input(
            "Every (seconds)", min_value=30, max_value=600, step=15,
            value=int(cfg.refresh_interval_seconds), key="sb_interval",
            help="How often the whole market is re-scraped while open. "
                 "Minimum 30s to stay gentle on dsebd.org.")
        if int(interval) != cfg.refresh_interval_seconds:
            monitor.update_refresh_interval(int(interval))
            flash(f"Refresh interval → {int(interval)}s", "⏱")

        if st.button("⚡ Refresh now", width="stretch", key="btn_refresh"):
            with st.spinner("Scraping the whole market…"):
                fresh = monitor.refresh_now()
            if fresh["last_refresh_success"]:
                flash(f"Updated {fresh['stock_count']} stocks", "⚡")
            else:
                flash(f"Refresh failed: {fresh['last_error']}", "❌")
            st.rerun()

        st.caption(f"Stocks loaded: **{snap['stock_count']}** · "
                   f"last refresh {fmt_ts(snap['last_refresh_time'])}")
        if snap["next_refresh_at"] and running:
            st.caption(f"Next refresh ≈ {snap['next_refresh_at'].strftime('%I:%M:%S %p').lstrip('0')}")

        st.divider()
        # ---- Twilio quick status ----
        if monitor.notifier.ready:
            st.success("WhatsApp alerts armed", icon="✅")
        else:
            st.warning("WhatsApp not configured — open **Settings**", icon="⚠️")
        st.caption("Data: dsebd.org · Times in Asia/Dhaka")
