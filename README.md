להעתיק מכאן (כולל השורה):

<div align="center">

<img src="https://raw.githubusercontent.com/github/explore/main/topics/solana/solana.png" width="80" />

# ⚡ Solana Grid Bot

### Intelligent Automated Futures Trading on Binance UM

<em>Continuous micro-profit execution, capital control, and volatility harvesting.</em>

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Exchange](https://img.shields.io/badge/Binance-UM%20Futures-yellow)
![Mode](https://img.shields.io/badge/Mode-DRY%20%7C%20TESTNET%20%7C%20LIVE-red)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Last Commit](https://img.shields.io/github/last-commit/Shmuel18/solana-grid-bot?color=orange)
![Stars](https://img.shields.io/github/stars/Shmuel18/solana-grid-bot?style=social)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

</div>

---

## 🔥 Why This Bot?

Most trading bots are:
❌ too complex  
❌ unreliable under volatility  
❌ emotionally influenced

**This bot is:**
✅ Simple  
✅ Fast  
✅ Emotionless  
✅ Capital-protected

Designed specifically for constant micro-profits and controlled exposure.

---

## 🚀 How It Works

Price dips → Buy ladder rung
Price rises → Take profit on that rung
Repeat forever

Each rung is independent — no full-position panic exits.

---

## 🧠 Architecture Overview

WebSocket Stream → Real-time Quotes
↓
Grid Logic → Ladder Checks & Spread Control
↓
Order Manager → HMAC-Signed REST Execution
↓
CSV Ledger → Backtest & Analytics

---

## 🧰 Tech Stack

- Python 3.10+
- Binance Futures REST (HMAC)
- Python WebSockets
- dotenv configuration
- CSV audit logging

---

## 📦 Project Structure

solana-grid-bot/
├─ bot.py # Core logic & event loop
├─ requirements.txt # Dependencies
├─ .env # Secrets & dynamic config
└─ trades.csv # Runtime trade ledger

---

## ⚙️ Configuration (`.env`)

````ini
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

SYMBOL=SOLUSDT
MODE=DRY                  # DRY | TESTNET | LIVE
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200.0
CSV_FILE=trades.csv
COPY_TRADE_ASSUMED_BALANCE=500.0


.gitignore already protects your secrets.

▶️ Running the Bot

Dry run (no real money):

python bot.py


Switch to Testnet:

MODE=TESTNET


Production:

MODE=LIVE

📊 Sample Runtime Output
[WS] Connected
Base price: 190
Filled BUY ladder #3 @ 187.40
Released profit rung #1 @ +$1.02
Open ladders: 3 | Daily spent: $43.00

🛡 Safety Systems

Max daily exposure guard

Spread threshold

Ladder limit

Clock drift protection

Dry mode simulation

Testnet environment

🧭 Roadmap

Multi-symbol grid

Short-grid mirrored logic

Telegram alerts

Prometheus metrics dashboard

Crash-resistant recovery

Volatility-adaptive spacing

🤝 Contributions

PRs welcome.
Please include:

Sanitized logs

Steps to reproduce

Expected vs actual output

📜 License

MIT — open for commercial & personal use.

<div align="center"> <h3>🟣 Automate your profits. Remove your emotions.</h3> <i>Built by someone who actually trades.</i> <br><br> ⭐ If this helped you — give it a star! </div>

<br/><br/>

<div dir="rtl" style="direction: rtl; text-align: right;"> <h2>⚡ בוט גריד אוטומטי למסחר ב-SOL על Binance Futures</h2> <p><strong>מערכת מסחר אוטומטית</strong> שמבצעת קניות מדורגות בירידות, מממשת רווחים קטנים בעליות, ומאפשרת מסחר רציף ללא מעורבות רגשית — תוך שמירה על גבולות סיכון ברורים.</p> <h3>🎯 למה דווקא הבוט הזה?</h3> <ul> <li>🔥 רווחים קטנים ומצטברים לאורך היום</li> <li>🔒 שליטה חכמה בהון ובלימות סיכון</li> <li>🤖 מסחר ללא רגש וללא שחיקה מנטלית</li> <li>⚙️ לוגיקה עצמאית לכל שלב (Ladder)</li> <li>🧠 התאמה טבעית לתנודתיות בשוק</li> </ul> <h3>🧬 איך זה עובד?</h3> <pre>מחיר יורד → קניית שלב קטן (Ladder) מחיר עולה → מימוש רווח רק על אותו שלב …וחוזר בלולאה אוטומטית</pre> <h3>🛡 מנגנוני הגנה</h3> <ul> <li>🛑 הגבלת חשיפה יומית</li> <li>📏 בדיקת מרווח (Spread) לפני ביצוע</li> <li>🧱 מספר שלבים מקסימלי</li> <li>⏱ בדיקת סטיית זמן לחתימות מדויקות</li> <li>🧪 DRY Mode — סימולציה ללא כסף אמיתי</li> <li>🧵 Testnet — סביבת ניסוי בחינם</li> </ul> <h3>⚠ אזהרת סיכון</h3> <p>מסחר בחוזים ממונפים עלול לגרום להפסדים משמעותיים. הקוד נועד ללמידה והתנסות — על אחריות המשתמש בלבד.</p> <p><em>✨ מסחר חכם מתחיל ממערכות שלא מתעייפות.</em></p> </div> ```
✅✅✅ עד כאן להעתיק (כולל השורה)<div align="center">

<img src="https://raw.githubusercontent.com/github/explore/main/topics/solana/solana.png" width="80" />

# ⚡ Solana Grid Bot
### Intelligent Automated Futures Trading on Binance UM

<em>Continuous micro-profit execution, capital control, and volatility harvesting.</em>

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Exchange](https://img.shields.io/badge/Binance-UM%20Futures-yellow)
![Mode](https://img.shields.io/badge/Mode-DRY%20%7C%20TESTNET%20%7C%20LIVE-red)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Last Commit](https://img.shields.io/github/last-commit/Shmuel18/solana-grid-bot?color=orange)
![Stars](https://img.shields.io/github/stars/Shmuel18/solana-grid-bot?style=social)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

</div>

---

## 🔥 Why This Bot?

Most trading bots are:
❌ too complex
❌ unreliable under volatility
❌ emotionally influenced

**This bot is:**
✅ Simple
✅ Fast
✅ Emotionless
✅ Capital-protected

Designed specifically for constant micro-profits and controlled exposure.

---

## 🚀 How It Works



Price dips → Buy ladder rung
Price rises → Take profit on that rung
Repeat forever


Each rung is independent — no full-position panic exits.

---

## 🧠 Architecture Overview



WebSocket Stream → Real-time Quotes
↓
Grid Logic → Ladder Checks & Spread Control
↓
Order Manager → HMAC-Signed REST Execution
↓
CSV Ledger → Backtest & Analytics


---

## 🧰 Tech Stack

- Python 3.10+
- Binance Futures REST (HMAC)
- Python WebSockets
- dotenv configuration
- CSV audit logging

---

## 📦 Project Structure



solana-grid-bot/
├─ bot.py # Core logic & event loop
├─ requirements.txt # Dependencies
├─ .env # Secrets & dynamic config
└─ trades.csv # Runtime trade ledger


---

## ⚙️ Configuration (`.env`)

```ini
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

SYMBOL=SOLUSDT
MODE=DRY                  # DRY | TESTNET | LIVE
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200.0
CSV_FILE=trades.csv
COPY_TRADE_ASSUMED_BALANCE=500.0


.gitignore already protects your secrets.

▶️ Running the Bot

Dry run (no real money):

python bot.py


Switch to Testnet:

MODE=TESTNET


Production:

MODE=LIVE

📊 Sample Runtime Output
[WS] Connected
Base price: 190
Filled BUY ladder #3 @ 187.40
Released profit rung #1 @ +$1.02
Open ladders: 3 | Daily spent: $43.00

🛡 Safety Systems

Max daily exposure guard

Spread threshold

Ladder limit

Clock drift protection

Dry mode simulation

Testnet environment

🧭 Roadmap

Multi-symbol grid

Short-grid mirrored logic

Telegram alerts

Prometheus metrics dashboard

Crash-resistant recovery

Volatility-adaptive spacing

🤝 Contributions

PRs welcome.
Please include:

Sanitized logs

Steps to reproduce

Expected vs actual output

📜 License

MIT — open for commercial & personal use.

<div align="center"> <h3>🟣 Automate your profits. Remove your emotions.</h3> <i>Built by someone who actually trades.</i> <br><br> ⭐ If this helped you — give it a star! </div>

<br/><br/>

<div dir="rtl" style="direction: rtl; text-align: right;"> <h2>⚡ בוט גריד אוטומטי למסחר ב-SOL על Binance Futures</h2> <p><strong>מערכת מסחר אוטומטית</strong> שמבצעת קניות מדורגות בירידות, מממשת רווחים קטנים בעליות, ומאפשרת מסחר רציף ללא מעורבות רגשית — תוך שמירה על גבולות סיכון ברורים.</p> <h3>🎯 למה דווקא הבוט הזה?</h3> <ul> <li>🔥 רווחים קטנים ומצטברים לאורך היום</li> <li>🔒 שליטה חכמה בהון ובלימות סיכון</li> <li>🤖 מסחר ללא רגש וללא שחיקה מנטלית</li> <li>⚙️ לוגיקה עצמאית לכל שלב (Ladder)</li> <li>🧠 התאמה טבעית לתנודתיות בשוק</li> </ul> <h3>🧬 איך זה עובד?</h3> <pre>מחיר יורד → קניית שלב קטן (Ladder) מחיר עולה → מימוש רווח רק על אותו שלב …וחוזר בלולאה אוטומטית</pre> <h3>🛡 מנגנוני הגנה</h3> <ul> <li>🛑 הגבלת חשיפה יומית</li> <li>📏 בדיקת מרווח (Spread) לפני ביצוע</li> <li>🧱 מספר שלבים מקסימלי</li> <li>⏱ בדיקת סטיית זמן לחתימות מדויקות</li> <li>🧪 DRY Mode — סימולציה ללא כסף אמיתי</li> <li>🧵 Testnet — סביבת ניסוי בחינם</li> </ul> <h3>⚠ אזהרת סיכון</h3> <p>מסחר בחוזים ממונפים עלול לגרום להפסדים משמעותיים. הקוד נועד ללמידה והתנסות — על אחריות המשתמש בלבד.</p> <p><em>✨ מסחר חכם מתחיל ממערכות שלא מתעייפות.</em></p> </div> ```
````
