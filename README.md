# 📈 DSE Stock Monitor — OLYMPIC

A production-ready **Streamlit** dashboard that monitors the **Dhaka Stock
Exchange (DSE)** latest share price page, tracks **OLYMPIC**'s LTP every
2 minutes during trading hours, and sends **WhatsApp alerts** (via Twilio)
when the price enters your target range — with built-in **AI anomaly
detection**, full logging, and a premium glassmorphism UI.

Data source: <https://www.dsebd.org/latest_share_price_scroll_l.php>

---

## ✨ Features

| Feature | Details |
|---|---|
| **Scraping** | `requests` + `BeautifulSoup` first; automatic Playwright/Selenium fallback if the page becomes dynamic; last-resort text-proximity extraction near "OLYMPIC" |
| **Condition alerts** | WhatsApp message when `143 ≤ LTP ≤ 145` (range editable live in the sidebar) |
| **Dedupe** | No duplicate alerts for the same unchanged price (configurable), plus a cooldown |
| **Trading hours** | Sun–Thu, continuous 10:00 AM–2:20 PM + post-closing 2:20–2:30 PM (Asia/Dhaka); automatic pause outside these hours |
| **Emergency collection** | ⚡ *Collect Data Now* button scrapes instantly — full pipeline (AI + alerts + logging) without waiting for the next scheduled poll |
| **AI analysis** | IsolationForest + robust z-score + >2% spike/drop rule on the last 20 prices; runs on a worker thread so it never blocks alerts |
| **Error handling** | Per-scrape retries; after 3 consecutive failures: WhatsApp error alert + auto-pause + prominent dashboard banner |
| **Logging** | Every scrape → SQLite (`dse_monitor.db`) **and** CSV (`scrape_log.csv`): timestamp, LTP, success, alert sent, AI status |
| **UI** | Glassmorphism cards, gradients, KPI tiles, live Plotly chart, alert history, auto-refresh every 10 s |

> ⚠️ WhatsApp **messages only**. This project contains **no** Twilio Voice or
> phone-call functionality whatsoever.

---

## 📂 Project Structure

```
DSE/
├── app.py                 # Streamlit dashboard (UI + controls)
├── scraper.py             # DSE scraping with fallbacks & retries
├── notifier.py            # Twilio WhatsApp messaging (no voice)
├── ai_analyzer.py         # Anomaly detection (IsolationForest + z-score + rule)
├── scheduler.py           # Background monitoring thread
├── database.py            # SQLite + CSV logging
├── config.py              # Configuration loading (.env / secrets / json)
├── utils.py               # Trading hours, timezone, logging helpers
├── requirements.txt
├── .env.example           # Copy to .env and fill in
├── config.json.example    # Copy to config.json (optional, non-secret tunables)
└── README.md
```

---

## 🚀 Quick Start (local)

```bash
# 1. Clone / copy the project, then create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
copy .env.example .env            # Windows  (cp on macOS/Linux)
copy config.json.example config.json
# ...edit .env with your Twilio credentials and numbers

# 4. Run
streamlit run app.py
```

Open <http://localhost:8501> and press **▶ Start Tracking**. Outside
market hours, use **⚡ Collect Data Now** to test an instant collection.

---

## 📱 Twilio WhatsApp Setup Guide

1. **Create a Twilio account** at <https://www.twilio.com/try-twilio> (free trial works).
2. In the **Twilio Console**, copy your **Account SID** and **Auth Token**
   (Dashboard → Account Info).
3. Open **Messaging → Try it out → Send a WhatsApp message** to activate the
   **WhatsApp Sandbox**. Twilio shows a sandbox number, usually
   `+1 415 523 8886`, and a join code like `join <two-words>`.
4. From **your own WhatsApp**, send `join <two-words>` to that sandbox
   number. You'll receive a confirmation. (Sandbox joins expire after
   72 hours of inactivity — just re-send the join message.)
5. Fill in `.env`:
   ```ini
   TWILIO_ACCOUNT_SID=ACxxxxxxxx...
   TWILIO_AUTH_TOKEN=xxxxxxxx...
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   RECIPIENT_WHATSAPP_NUMBER=whatsapp:+8801XXXXXXXXX
   ```
   The `whatsapp:` prefix is added automatically if you omit it.
6. Restart the app and click **"Send test WhatsApp message"** in the sidebar
   to verify end-to-end delivery.
7. **Production:** for unlimited messaging without the sandbox, request a
   Twilio-approved WhatsApp sender (Messaging → Senders → WhatsApp senders)
   and put that number in `TWILIO_WHATSAPP_NUMBER`.

Alert format sent by the app:

```
🔔 DSE Alert: OLYMPIC LTP = 144.2
Condition: 143-145
Time: 2026-06-10 11:42:00
AI Note: Sudden spike (+2.40% in one interval)   ← only when detected
```

---

## ☁️ Streamlit Cloud Deployment

1. Push this project to a **GitHub repository** (make sure `.env`,
   `config.json`, `dse_monitor.db`, and `scrape_log.csv` are in `.gitignore`).
2. Go to <https://share.streamlit.io> → **New app** → pick your repo,
   branch, and `app.py`.
3. In **App → Settings → Secrets**, paste your configuration as TOML:
   ```toml
   TWILIO_ACCOUNT_SID = "ACxxxxxxxx"
   TWILIO_AUTH_TOKEN = "xxxxxxxx"
   TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"
   RECIPIENT_WHATSAPP_NUMBER = "whatsapp:+8801XXXXXXXXX"
   TARGET_MIN_PRICE = "143"
   TARGET_MAX_PRICE = "145"
   AI_ENABLED = "true"
   ```
4. Deploy. The app reads `st.secrets` automatically (it takes precedence
   over `.env` and `config.json`).

**Notes for Streamlit Cloud**

- The monitoring loop runs in a background thread inside the app process.
  Streamlit Cloud puts idle apps to sleep, so for 24/7 unattended
  monitoring keep the browser tab open, use an uptime pinger, or deploy to
  an always-on host (Railway, Render, a VPS with
  `streamlit run app.py --server.port 8501`).
- SQLite/CSV files are ephemeral on Streamlit Cloud — logs reset on
  redeploy. Use a VPS if you need durable history.
- The headless-browser fallback is optional; the DSE page is static HTML,
  so the default `requests` path works on Cloud without extra packages.

---

## 🤖 Enable / Disable AI Analysis

The AI module (IsolationForest + robust z-score + 2% spike/drop rule) is
controlled by one flag:

- **.env:** `AI_ENABLED=true` or `AI_ENABLED=false`
- **config.json:** `"ai_enabled": true/false`
- **Streamlit Cloud secrets:** `AI_ENABLED = "false"`

Restart the app after changing it. Related tunables:

| Key | Default | Meaning |
|---|---|---|
| `AI_SPIKE_THRESHOLD_PCT` | `2.0` | % move within one 2-min poll that triggers a spike/drop alert |
| `AI_HISTORY_SIZE` | `20` | Rolling window of recent LTP values analysed |

When an anomaly is detected, a **separate WhatsApp alert** is sent
immediately — even if the price hasn't reached the target range.

---

## ⚙️ All Configuration Keys

| Key (env / json) | Default | Description |
|---|---|---|
| `TRADING_CODE` | `OLYMPIC` | DSE trading code to track |
| `TARGET_MIN_PRICE` / `TARGET_MAX_PRICE` | `143` / `145` | Inclusive alert range (also editable live in the sidebar) |
| `POLLING_INTERVAL_SECONDS` | `120` | Scrape frequency |
| `TRADING_START` / `TRADING_END` | `10:00` / `14:30` | Full monitoring window incl. post-close (Asia/Dhaka) |
| `TRADING_CONTINUOUS_END` | `14:20` | End of continuous trading (post-close runs until `TRADING_END`) |
| `trading_days` (json only) | `[6,0,1,2,3]` | Sun–Thu (Mon=0 … Sun=6) |
| `MAX_CONSECUTIVE_FAILURES` | `3` | Failures before error alert + auto-pause |
| `REALERT_ON_SAME_PRICE` | `false` | Re-send alerts for an unchanged price |
| `ALERT_COOLDOWN_SECONDS` | `600` | Minimum gap between target alerts |
| `AI_ENABLED` | `true` | Toggle anomaly detection |

Precedence: **Streamlit secrets → environment / .env → config.json → defaults**.

---

## 🧪 Testing Without the Market

1. Press **⚡ Collect Data Now** — it scrapes instantly, even while the
   market is closed, and runs the full alert pipeline.
2. Widen the target range (e.g. `100 – 200`) in the sidebar to force a
   target alert on the next collection.
3. Use the sidebar **"Send test WhatsApp message"** button to verify Twilio
   independently of scraping.

## 🛡️ Disclaimer

This tool is for personal informational use. It is not financial advice.
Respect dsebd.org's terms of service; the default 2-minute polling interval
is deliberately gentle.
