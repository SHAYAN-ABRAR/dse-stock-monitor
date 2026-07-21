"""
views/bulk_download.py
----------------------
Bulk Report Download — export the full DSE company report (every table
on the company page + the Closing Price / Total Trade / Total Volume
graphs at 2 years) for ANY set of stocks, or the entire market, as one
file in three formats: a machine-parsable flat CSV data table (one
fixed-schema row per data point — loads straight into Excel / pandas /
AI tools), the human-readable CSV report layout, or an Excel workbook.

The per-stock content is identical to the dashboard cards' Download
button (see company.py); this page bundles many stocks into one file.
Layout keeps everything above the fold: one control bar (search ·
select all · clear · the single Download dropdown with the three format
options), the progress / ready banner right under it, then the
scrollable checkbox grid — so the Download button never has to be
scrolled to. Reports are fetched concurrently but gently.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from company import (BULK_MAX_WORKERS, fetch_reports_bulk,
                     reports_to_csv_bytes, reports_to_excel_bytes,
                     reports_to_flat_csv_bytes)
from runtime import get_monitor, hero

# The three export formats. "flat" is one machine-parsable table (for
# Excel / pandas / AI analysis); "csv" is the human-readable report
# layout; "xlsx" the styled workbook.
FMT_BUILDER = {"flat": reports_to_flat_csv_bytes,
               "csv": reports_to_csv_bytes,
               "xlsx": reports_to_excel_bytes}
FMT_LABEL = {"flat": "CSV data table", "csv": "CSV report", "xlsx": "Excel"}
FMT_EXT = {"flat": "csv", "csv": "csv", "xlsx": "xlsx"}
FMT_STEM = {"flat": "DSE_bulk_data", "csv": "DSE_bulk_report",
            "xlsx": "DSE_bulk_report"}

monitor = get_monitor()

hero("Bulk Report Download",
     "Every table + 2-year graphs per stock · pick any set, or ☑ Select all "
     "~396, and export as one file — flat CSV data table (analysis-ready), "
     "CSV report, or Excel")

quotes = monitor.all_quotes()
if not quotes:
    st.warning("Market data is still loading — use **⚡ Refresh now** in the "
               "sidebar.")
    st.stop()

all_codes = [q.code for q in quotes]

# The selection lives in ONE session set (not in the checkbox widgets):
# Streamlit drops a widget's state the moment it isn't rendered, and the
# search box hides most checkboxes most of the time. Each checkbox seeds
# from — and writes back to — this set.
sel: set = st.session_state.setdefault("bulkdl_sel", set())
sel.intersection_update(all_codes)  # drop codes no longer listed


def _toggle(code: str) -> None:
    if st.session_state.get(f"bulkdl_cb_{code}"):
        sel.add(code)
    else:
        sel.discard(code)


def _queue_job(codes: list, fmt: str) -> None:
    st.session_state["_bulkdl_job"] = {"codes": codes, "fmt": fmt}
    st.session_state.pop("_bulkdl_ready", None)
    # Popovers can't be closed programmatically — remount it closed.
    st.session_state["_bulkdl_nonce"] = nonce + 1
    st.rerun()


# ======================================================================
# Control bar: search · select all · clear · THE Download dropdown.
# Everything actionable sits here, above the grid — no scrolling to find
# the download button.
# ======================================================================
st.markdown('<div class="section-title">📋 Choose stocks & download</div>',
            unsafe_allow_html=True)

nonce = st.session_state.get("_bulkdl_nonce", 0)
top = st.columns([2.4, 1.05, 0.95, 1.6], gap="small",
                 vertical_alignment="center")
term = top[0].text_input(
    "Search stocks", key="bulkdl_search",
    placeholder="🔍 Search by trading code, sector or #index…",
    label_visibility="collapsed")

t = term.strip().lower()
shown = ([q for q in quotes
          if t in q.code.lower() or t in q.sector.lower()
          or t == str(q.index)]
         if t else quotes)

# These buttons render BEFORE the download popover and the checkboxes, so
# pushing the new state into the (already-existing) checkbox keys here is
# picked up on this same run — the Download count updates instantly too.
if top[1].button(f"☑ Select {'shown' if t else 'all'} ({len(shown)})",
                 width="stretch", key="bulkdl_select_all",
                 disabled=not shown,
                 help="Tick every stock currently listed in the grid below"):
    for q in shown:
        sel.add(q.code)
        st.session_state[f"bulkdl_cb_{q.code}"] = True
if top[2].button("☐ Clear", width="stretch", key="bulkdl_clear",
                 disabled=not sel, help="Untick everything"):
    for q in shown:
        st.session_state[f"bulkdl_cb_{q.code}"] = False
    sel.clear()

selected_codes = [q.code for q in quotes if q.code in sel]  # market order
n_sel = len(selected_codes)
label = (f"Download ({n_sel} of {len(all_codes)})"
         if n_sel else "Download — select stocks first")
with top[3].popover(label, icon=":material/download:", width="stretch",
                    disabled=not selected_codes, key=f"bulkdl_pop_{nonce}"):
    st.caption(f"**{n_sel} stocks** — full DSE company page (every table) + "
               "the three 2-year graphs per stock, in one file.")
    if st.button("CSV — data table (for analysis)", icon=":material/dataset:",
                 width="stretch", key="bulkdl_flat",
                 help="One flat table (six fixed columns, one row per data "
                      "point) that loads straight into Excel, pandas or an "
                      "AI tool — the machine-readable choice"):
        _queue_job(selected_codes, "flat")
    if st.button("CSV — formatted report", icon=":material/csv:",
                 width="stretch", key="bulkdl_csv",
                 help="Human-readable layout mirroring the DSE company page, "
                      "one block per stock — for reading, not parsing"):
        _queue_job(selected_codes, "csv")
    if st.button("Excel workbook", icon=":material/table_view:",
                 width="stretch", key="bulkdl_xlsx",
                 help="Styled workbook: Overview sheet + one sheet per stock"):
        _queue_job(selected_codes, "xlsx")

st.caption(f"Tick stocks below (selection survives searching) — or "
           f"**☑ Select all** for the whole market. Each report is fetched "
           f"fresh from dsebd.org (4 pages per stock, {BULK_MAX_WORKERS} at "
           "a time), so all ~396 take a few minutes. Keep this page open "
           "while it builds.")

# ---- Build phase: fetch with progress, then hand over the bytes ------
# Rendered here, right under the control bar, so it's visible on click.
job = st.session_state.pop("_bulkdl_job", None)
if job:
    codes, fmt = job["codes"], job["fmt"]
    total = len(codes)
    progress = st.progress(0.0, text=f"Fetching 0 / {total} company reports…")

    def _on_progress(done: int, n: int, code: str) -> None:
        progress.progress(done / n,
                          text=f"Fetching {done} / {n} company reports — "
                               f"latest: {code}")

    reports, failures = fetch_reports_bulk(codes, progress_cb=_on_progress)
    progress.progress(1.0, text=f"Fetched {len(reports)} / {total} — "
                                f"building the {FMT_LABEL[fmt]} file…")
    with st.spinner(f"Structuring {len(reports)} reports into one "
                    f"{FMT_LABEL[fmt]} file…"):
        data = FMT_BUILDER[fmt](reports, failures)
    st.session_state["_bulkdl_ready"] = {
        "bytes": data, "fmt": fmt,
        "count": len(reports), "failures": failures,
        "stamp": datetime.now().strftime("%Y-%m-%d_%H%M"),
    }
    st.rerun()

# ---- Ready phase: the finished file, one click away ------------------
ready = st.session_state.get("_bulkdl_ready")
if ready:
    fmt, count = ready["fmt"], ready["count"]
    size_mb = len(ready["bytes"]) / 1_000_000
    r1, r2, r3 = st.columns([2.2, 1.6, 0.5], gap="small",
                            vertical_alignment="center")
    r1.success(f"**{FMT_LABEL[fmt]} ready** — {count} stocks · "
               f"{size_mb:.1f} MB", icon="✅")
    r2.download_button(
        f"💾 Save {FMT_LABEL[fmt]}",
        data=ready["bytes"],
        file_name=(f"{FMT_STEM[fmt]}_{count}stocks_{ready['stamp']}"
                   f".{FMT_EXT[fmt]}"),
        mime=("text/csv" if FMT_EXT[fmt] == "csv"
              else "application/vnd.openxmlformats-officedocument"
                   ".spreadsheetml.sheet"),
        type="primary", width="stretch", on_click="ignore",
        key="bulkdl_save")
    if r3.button("✕", width="stretch", key="bulkdl_discard",
                 help="Drop the built file to free memory"):
        st.session_state.pop("_bulkdl_ready", None)
        st.rerun()
    if ready["failures"]:
        st.warning(
            f"{len(ready['failures'])} stock(s) could not be fetched and are "
            "listed in the file under FAILED STOCKS: "
            + ", ".join(code for code, _ in ready["failures"]),
            icon="⚠️")

# ======================================================================
# Checkbox grid (scrollable, styled via st-key-bulkdl_grid)
# ======================================================================
with st.container(height=400, border=True, key="bulkdl_grid"):
    if not shown:
        st.info(f"No stock matches “{term.strip()}”.")
    GRID = 4
    for start in range(0, len(shown), GRID):
        cols = st.columns(GRID, gap="small")
        for col, q in zip(cols, shown[start:start + GRID]):
            key = f"bulkdl_cb_{q.code}"
            if key not in st.session_state:
                st.session_state[key] = q.code in sel
            col.checkbox(f"{q.index}. **{q.code}**", key=key,
                         on_change=_toggle, args=(q.code,),
                         help=q.sector or "DSE listed security")
