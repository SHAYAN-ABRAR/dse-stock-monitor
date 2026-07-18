"""
app.py
------
DSE Terminal — multi-stock monitoring platform (Version 2).

Entry point. Sets up the page, the global premium theme, the shared
sidebar control panel, and the multi-view navigation. The heavy lifting
(scraping the whole market, storing history, evaluating alerts, sending
WhatsApp notifications) runs in a background thread owned by the
process-wide ``MarketMonitor`` singleton (see runtime.get_monitor).

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="DSE Terminal — Live Market Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from runtime import (get_monitor, get_theme, inject_theme,  # noqa: E402
                     render_flash, render_sidebar)
from utils import setup_logging  # noqa: E402

setup_logging()

monitor = get_monitor()
inject_theme(get_theme(monitor))

# First paint: make sure the market cache is populated so every view has
# data to show. Cheap on subsequent runs (returns immediately when ready).
if not monitor.market_ready():
    with st.spinner("Loading the Dhaka Stock Exchange market…"):
        monitor.ensure_loaded()

# ---- Multi-view navigation (modern st.navigation API) ----
overview = st.Page("views/overview.py", title="Market Overview",
                   icon=":material/dashboard:")
dashboard = st.Page("views/dashboard.py", title="My Dashboard",
                    icon=":material/grid_view:", default=True)
details = st.Page("views/details.py", title="Stock Details",
                  icon=":material/insights:")
watchlists = st.Page("views/watchlists.py", title="Watchlists",
                     icon=":material/star:")
bulk_download = st.Page("views/bulk_download.py", title="Bulk Download",
                        icon=":material/download:")
settings = st.Page("views/settings.py", title="Settings",
                   icon=":material/settings:")

nav = st.navigation([dashboard, overview, details, watchlists,
                     bulk_download, settings])

# Shared chrome rendered under the navigation on every view.
render_sidebar(monitor)

nav.run()

# Top-toast notifications (slide down, hold ~1.5s, slide up). Rendered last
# so actions that don't trigger a rerun still surface their toast this pass.
render_flash()
