<div align="center">

<img src="https://raw.githubusercontent.com/github/explore/main/topics/solana/solana.png" width="80" />

# ⚡ Solana Grid Bot

### Intelligent Automated Futures Trading on Binance UM

<p>
<em>Continuous micro-profit execution, capital control, and volatility harvesting.</em>
</p>

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Exchange](https://img.shields.io/badge/Binance-UM%20Futures-yellow)
![Mode](https://img.shields.io/badge/Mode-DRY%20%7C%20TESTNET%20%7C%20LIVE-red)
![Status](https://img.shields.io/badge/Status-Production-ready-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

</div>

---

## 🔥 Why This Bot?

Most DCA grid bots are bloated, overcomplicated, and fail under real volatility.  
This bot is different:

✅ Minimal latency (WebSockets)  
✅ Micro profit-taking per ladder rung  
✅ Daily capital guardrails  
✅ Spread protection (bps)  
✅ Copy-Trading friendly  
✅ Zero dependencies beyond core libs

It’s engineered for **reliable**, **controlled**, **continuous** accumulation.

---

## 🚀 Core Logic (At a Glance)

Price drops → ladder buys
Price rebounds → release profit
Repeat forever

Each ladder is independent — no “all-or-nothing” exits.

---

## 🧠 Architecture

WebSocket → Live Quote Engine
↓
Price Logic → Grid Ladder Checks
↓
Order Manager → Signed REST Execution
↓
CSV Event Stream → Analytics / Backtest

---

## 🧰 Tech Stack

- Python 3.10+
- Binance REST (HMAC)
- Binance WebSocket streams
- CSV logging
- dotenv config

Lightweight, battle-tested, maintainable.

---

## 📦 Project Layout

solana-grid-bot/
├─ bot.py # Main event loop + strategy
├─ requirements.txt # Dependencies
├─ .env # Secrets + dynamic config
└─ trades.csv # Runtime trade ledger

---

## ⚙️ Configuration (`.env`)

BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

SYMBOL=SOLUSDT
MODE=DRY # DRY | TESTNET | LIVE
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200.0
CSV_FILE=trades.csv
COPY_TRADE_ASSUMED_BALANCE=500.0

---

## ▶️ Run

Dry (no real orders):

````bash
python bot.py


Testnet:

MODE=TESTNET


Production money:

MODE=LIVE

📊 Example Output
[WS] Connected
Base Price: 190
Filled BUY ladder #3 @ 187.40
Released profit rung #1 @ +$1.02
Open ladders: 3 | Daily spent: $43.00


Clear. Fast. Surgical.

🛡 Safety Nets

Max daily exposure cap

Spread constraint

Ladder limit

Single-rung TP

Dry run mode

Testnet simulation

Hard fail if clock drifted

Because risk is a feature, not an afterthought.

🐛 Troubleshooting
Issue	Fix
Orders not placed	Lower spread threshold
Insufficient margin	Reduce ladder qty
Timestamp rejected	Sync OS time
Copy-Trading API restricted	Use assumed balance flag
🧭 Roadmap

Multi-symbol engine

Short-grid mirrored logic

Telegram live alerts

Prometheus metrics

Crash-resistant recovery

Volatility adaptive ladder spacing

🤝 Contributions

PRs welcome — please include:

Logs (sanitize secrets)

Steps to reproduce

Expected vs actual behavior

⚠ Disclaimer

This repository is for educational purposes only.
Crypto derivatives involve significant risk.
Trade responsibly.

<div align="center"> <h3>🟣 Automate your profits, remove your emotions.</h3> <i>Built by someone who actually trades.</i> <br><br> ⭐ If this helped you — leave a star, it matters! </div>
🇮🇱 גרסה בעברית
<div dir="rtl">
⚡ בוט גריד למסחר אוטומטי ב-SOLUM על Binance Futures

בוט קל, מהיר ויציב שמבצע:

קניות מדורגות בירידה

סגירת רווחים קטנים בכל שלב

הגבלת הון יומית

ניהול ספראד

הרצה יבשה ו-Testnet

כל אירוע נרשם ל-CSV לניתוח מאוחר.

הבוט מיועד לסקאלפינג מתמשך, רווחים קטנים מצטברים ושליטה מדויקת בסיכון.

⚠ מסחר ממונף כרוך בסיכון — השתמש באחריות.

</div> ```
````
