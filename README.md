# 📈 DSE Terminal — Live Multi-Stock Monitoring Platform

A production-ready **Streamlit** platform that monitors the **entire Dhaka
Stock Exchange (DSE)** — all ~396 listed instruments — in real time. Browse
and search every stock, build a personal dashboard of live glassmorphic
cards, open deep-dive analytics with professional charts, save watchlists,
and get **WhatsApp alerts** (via Twilio) the moment a price condition is met
— all wrapped in a premium, client-ready interface.

Data source: <https://www.dsebd.org/latest_share_price_scroll_l.php>
(one request returns the whole market).

> This is **Version 2** — a complete expansion of the original single-stock
> (OLYMPIC) monitor into a full portfolio-style platform.

---

## ✨ Features

| Area | What you get |
|---|---|
| **Whole-market data** | One scrape pulls all ~396 stocks: index #, code, LTP, high, low, close, prev-close (YCP), change, change %, trades, value, volume |
| **Market Overview** | Live breadth (advancers/decliners), turnover & volume KPIs, top gainers / losers / most-active, and a searchable table of every instrument |
| **Searchable multi-select** | Pick any number of stocks by trading code or index number (type-ahead, keyboard nav, multi-select) |
| **Live dashboard** | Selected stocks render as responsive, colour-coded **glass cards** (green up / red down / blue flat) that auto-refresh — hover animations & micro-interactions |
| **Deep-dive analytics** | Per-stock page: basic info, price data, trading activity, day-range indicator, performance gauge (bullish/neutral/bearish), AI momentum, and Plotly charts (live price trend, volume, price-vs-volume) |
| **Historical storage** | Tracked stocks are recorded to **SQLite** (`dse_market.db`) for trend charts & analysis |
| **Watchlists** | Create / load / delete named groups ("Banking", "High Volume", …); load one onto the dashboard in a click |
| **Price alerts** | Per-stock rules — `above`, `below`, `enters a band`, `exits a band` — with per-rule cooldown; fires a **WhatsApp** message and logs every alert |
| **AI anomaly detection** | IsolationForest + robust z-score + spike/drop rule per tracked stock, surfaced as a momentum indicator |
| **Real-time** | Background thread re-scrapes the market on a configurable cadence; cards & charts update without a full page reload |
| **Premium UI** | Glassmorphism, gradient accents, animated hero, live Dhaka clock with market-open/close countdown, custom scrollbars, refined typography |

> ⚠️ Alerts are **WhatsApp messages only**. This project contains **no**
> Twilio Voice / phone-call functionality whatsoever.

---

## 📂 Project Structure

```
DSE/
├── app.py                  # Entry: page config, theme, st.navigation, sidebar
├── runtime.py              # Cached MarketMonitor singleton + shared chrome
│
├── views/                  # One file per navigation page
│   ├── overview.py         #   Market Overview (landing)
│   ├── dashboard.py        #   My Dashboard (multi-stock live cards)
│   ├── details.py          #   Stock Details (deep-dive analytics)
│   ├── watchlists.py       #   Watchlists (CRUD)
│   ├── alerts.py           #   Alert rules + history
│   └── settings.py         #   Twilio setup, test message, status
│
├── components/             # Reusable UI building blocks
│   ├── styles.py           #   Global premium CSS theme
│   ├── cards.py            #   Stock-card grid renderer
│   ├── charts.py           #   Plotly charts (trend, volume, gauge, range)
│   └── detail.py           #   Detailed analytics view
│
├── market.py               # MarketScraper — full-table scrape → StockQuote[]
├── market_db.py            # MarketRepository — SQLite (snapshot/history/rules/…)
├── market_monitor.py       # Background engine: refresh + alerts + AI
│
├── config.py               # Configuration (.env / secrets / json / user settings)
├── notifier.py             # Twilio WhatsApp messaging (no voice)
├── ai_analyzer.py          # Anomaly detection (IsolationForest + z-score + rule)
├── utils.py                # Trading hours, timezone, formatting helpers
├── certs/                  # Bundled DSE intermediate CA (TLS chain fix)
├── requirements.txt
├── .env.example            # Copy to .env and fill in
└── README.md
```

The legacy single-stock modules (`scraper.py`, `scheduler.py`,
`database.py`) remain in the repo for reference but are not used by the V2
entry point.

---

## 🚀 Quick Start (local)

```bash
# 1. Create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) configure Twilio up front — or do it later in the UI
copy .env.example .env            # Windows  (cp on macOS/Linux)
# ...edit .env with your Twilio credentials and numbers

# 4. Run
streamlit run app.py
```

Open <http://localhost:8501>. The whole market loads on first paint. Add
stocks from **Market Overview** or **My Dashboard**, then watch the live
cards. Everything (Twilio credentials, refresh interval, selections,
watchlists, alert rules) can be configured **inside the app** — no restart
needed.

---

## 🧭 Using the Platform

1. **Market Overview** — the landing page. See market breadth, top movers,
   and browse/search every stock. Use **➕ Add stocks to your dashboard**.
2. **My Dashboard** — your selected stocks as live cards. Search-and-add
   more from the multi-select; click **View Details** on any card.
3. **Stock Details** — full analytics + charts for any stock. **Track** a
   stock here to start recording its history (charts fill in over a few
   refresh cycles).
4. **Watchlists** — save themed groups and load them onto the dashboard.
5. **Alerts** — create price rules; matches fire a WhatsApp message.
6. **Settings** — Twilio credentials, **test message**, refresh cadence,
   and data status.

Use the **sidebar** to Start/Stop live monitoring, set the refresh
interval, and **⚡ Refresh now** (which collects a data point on demand,
even while the market is closed).

---

## 📱 Twilio WhatsApp Setup

You can enter everything directly in **Settings → WhatsApp Notifications**
(saved on the device, survives restarts), or pre-fill `.env`:

```ini
TWILIO_ACCOUNT_SID=ACxxxxxxxx...
TWILIO_AUTH_TOKEN=xxxxxxxx...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
RECIPIENT_WHATSAPP_NUMBER=whatsapp:+8801XXXXXXXXX
```

1. Create a free Twilio account → copy **Account SID** + **Auth Token**.
2. **Messaging → Try it out → Send a WhatsApp message** activates the
   **Sandbox** (number usually `+1 415 523 8886`, join code `join <words>`).
3. From the **recipient's** WhatsApp, send `join <words>` to the sandbox
   number once.
4. Enter the four values in **Settings**, then click **📨 Send test WhatsApp
   message** to verify delivery end-to-end.
5. **Production:** request a Twilio-approved WhatsApp sender for unlimited
   messaging without the sandbox.

Example alert:

```
📈 DSE Alert · OLYMPIC
LTP: 145 BDT
Change: +1.40%
Triggered: LTP ≥ 145
Time: 2026-06-16 11:42:00
```

---

## ⚙️ Configuration Keys

Precedence: **Streamlit secrets → environment / .env → config.json →
defaults**, with in-app changes (saved to `user_settings.json`) taking the
highest precedence.

| Key (env / json) | Default | Description |
|---|---|---|
| `SCRAPE_URL` | dsebd latest-share-price | Whole-market source page |
| `REFRESH_INTERVAL_SECONDS` | `60` | Market re-scrape cadence while open (min 30) |
| `HISTORY_RETENTION_DAYS` | `30` | Auto-prune price history older than this |
| `MARKET_DB_PATH` | `dse_market.db` | SQLite database location |
| `REQUEST_TIMEOUT_SECONDS` | `25` | HTTP timeout per scrape |
| `MAX_RETRIES_PER_SCRAPE` | `3` | Retries before a refresh is marked failed |
| `TRADING_START` / `TRADING_END` | `10:00` / `14:30` | Monitoring window incl. post-close (Asia/Dhaka) |
| `TRADING_CONTINUOUS_END` | `14:20` | End of continuous trading (display) |
| `trading_days` (json only) | `[6,0,1,2,3]` | Sun–Thu (Mon=0 … Sun=6) |
| `AI_ENABLED` | `true` | Toggle anomaly detection |
| `TWILIO_*`, `RECIPIENT_WHATSAPP_NUMBER` | — | WhatsApp credentials (or set in-app) |

---

## 🔐 TLS Note

`www.dsebd.org` omits its intermediate CA certificate from the TLS
handshake. The app ships that intermediate (`certs/`) and appends it to
certifi's trust store so certificate verification stays **fully enabled** —
no `verify=False` anywhere.

---

## ⚡ Performance

- One HTTP request refreshes the **entire** market (~396 stocks).
- The latest snapshot is held in memory for instant card/table rendering.
- **History is recorded only for tracked stocks** (selected + watchlisted +
  alert-rule stocks) to keep the database lean.
- Background thread + `st.cache_resource` singleton means scraping never
  blocks the UI; cards/charts refresh via Streamlit fragments.

---

## 🛡️ Disclaimer

For personal informational use only — not financial advice. Respect
dsebd.org's terms of service; the default refresh interval is deliberately
gentle.
