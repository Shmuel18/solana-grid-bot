# Solana Grid Bot — README

מדריך שימוש בסיסי לפרויקט `solana-grid-bot` (גרסה ראשונית — כולל דמו ובסיס לחיבור לבורסה).

תוכן
- מטרת הפרויקט
- מבנה הפרויקט
- התקנה והרצה (מהיר)
- דמו (בטוח)
- הרצת הבוט (dry-run) — בטוחה
- חיבור ל‑Testnet/אמיתי (זהירות)
- קונפיג ו‑env vars חשובים
- בדיקות ופיתוח
- נקודות בטיחות והמשך עבודה

---

מטרה
------
פרויקט זה מספק שלד לאסטרטגיית "גריד" (grid trading). מטרת הקוד: להיות מודולרי — שכבות ל־broker (בורסה), strategy (לוגיקת גריד), state (שמירת מצב), ו‑core (utils ו‑data stream). יש כאן דמו ובוט מינימלי שמריץ סימולציה (dry-run) כברירת מחדל.

מבנה פרויקט
-------------
- `bot.py` — נקודת כניסה (לולאת פולינג מינימלית). ברירת מחדל: dry-run.
- `config.py`, `config_example.py` — טעינת קונפיג/דוגמא.
- `broker/` — חיבור לבורסה (כרגע `binance_connector.py` עם מצב dry-run ותמיכה בסיסית ל‑Testnet).
- `strategy/` — `grid_logic.py` עם פונקציה טהורה לחישוב רמות.
- `state/` — `manager.py` (שמירה/טעינה אטומית של JSON).
- `core/` — `data_stream.py`, `utils.py`.
- `run_demo.py` — דמו שמדגים את חישוב הרמות ושימוש ב‑connector במצב dry-run.
- `tests/` — בדיקות בסיסיות (pytest).

מהירות התקנה והרצה
-------------------
הנחה: יש לך Python (מומלץ 3.10+) ו‑virtualenv. הפרויקט מכיל `.venv` מקומי בסביבת העבודה שהוגדרה כבר. אם לא — צור virtualenv והתקן דרישות.

התקנת דרישות (אם לא מותקנות):

```cmd
C:\> python -m venv .venv
C:\> .venv\Scripts\activate
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

להרצת הבדיקות המקומיות:

```cmd
.venv\Scripts\python.exe -m pytest -q
```

דמו (בטוח)
--------------
דמו מקומי שמחשב רמות גריד ומדגים שימוש ב‑connector במצב dry-run:

```cmd
.venv\Scripts\python.exe run_demo.py
```

הרצת הבוט (dry-run — בטוח)
--------------------------------
הבוט ברירת מחדל מריץ בסימולציה (אין הזמנות אמיתיות). הפעלת ברירת המחדל:

```cmd
.venv\Scripts\python.exe bot.py
```

אתה יכול לשנות פרמטרים כמו `mid`, `grid-size`, `spacing` ו‑`interval`:

```cmd
.venv\Scripts\python.exe bot.py --mid 100 --grid-size 7 --spacing 0.5 --interval 1.0
```

הערה: במצב dry-run ה‑connector מחקה הזמנות ולכן אין סיכון כספי.

חיבור ל‑Testnet / אמיתי (זהירות)
----------------------------------
לפני חיבור ל‑Testnet/אמיתי — בצע בדיקות מלאות ותוודא שאתה מבין את הסיכונים.

להרצת Testnet (דוגמה): הגדר מפתחות טסט ב‑env ואז כבה את ה‑dry-run:

```cmd
set BINANCE_API_KEY=your_test_key
set BINANCE_API_SECRET=your_test_secret
.venv\Scripts\python.exe bot.py --no-dry-run --testnet
```

הערות חשובות לפני חיבור אמיתי:
- ודא שה‑`binance_connector` כולל retry/backoff ו‑rate-limiting (כרגע יש צורך בשדרוג) 
- התחל תמיד ב‑Testnet
- הוסף הגבלות בטיחות (max notional, confirmation flag) לפני הפעלת פרודקשן

קונפיג ו‑Env vars (חשובים)
---------------------------
- `BINANCE_API_KEY` — מפתח API לבורסה (אל תשתף/אל תדחף לקוד)
- `BINANCE_API_SECRET` — סוד ה‑API
- `BINANCE_USE_TESTNET` — אם מוגדר ל‑`yes`/`true` נחבר ל‑testnet
- `DRY_RUN` — אם מוגדר ל‑`no` לא נשתמש ב‑dry-run (אבל `bot.py` מציע `--no-dry-run` גם כן)
- `STATE_PATH` — שם קובץ לשמירת מצב (ברירת מחדל: `bot_state.json`)
- `CSV_FILE` — קובץ רישום עסקאות (ברירת מחדל: `trades.csv`)

בדיקות ופיתוח
---------------
- יש בדיקות בסיסיות ב‑`tests/` עבור `strategy.grid_logic`. הרץ עם `pytest`.
- להרחבת הבדיקות: מומלץ להוסיף mocking ל‑`requests` כדי לבדוק `binance_connector` בלי לעשות קריאות רשת.

נקודות בטיחות והמשך עבודה מומלצת
----------------------------------
1. הוסף retry/backoff ו‑rate-limiting ל‑`broker/binance_connector.py`.
2. הוסף flag `--confirm-live` שמצריך אישור ידני לפני הפעלת מצב חי.
3. הוסף לוגינג מתקדם ו‑rolling logs.
4. שקול שימוש ב‑SQLite במקום CSV אם המצב גדל.
5. כיסוי בדיקות ל‑state manager ובדיקות אינטגרציה מדומות.

תרומה ופיתוח
--------------
אם תרצה שאממש שדרוגים (retry/backoff, rate‑limiter, `--confirm-live`, שדרוג לביצועים אסינכרוניים), תגיד לי מה להוסיף ואיישם זאת עבורך.

רישיון
-------
קוד זה משוחרר כדוגמה — אין כאן אחריות על תוצאות מסחריות. השתמש על אחריותך.

*** קצה README ***

קבצים שיצרנו עבורך: `bot.py`, `run_demo.py`, `broker/binance_connector.py`, `strategy/grid_logic.py`, `state/manager.py`, `core/*`, `tests/*` ועוד. README זה נוצר כדי להנחות שימוש ראשוני ובדיקות בטוחות.

*** סוף README ***
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

```
Price dips  → Buy ladder rung
Price rises → Take profit on that rung
Repeat forever
```

Each rung is independent — no full-position panic exits.

---

## 🧠 Architecture Overview

```
WebSocket Stream → Real-time Quotes
          ↓
Grid Logic → Ladder Checks & Spread Control
          ↓
Order Manager → HMAC-Signed REST Execution
          ↓
CSV Ledger → Backtest & Analytics
```

---

## 🧰 Tech Stack

- Python 3.10+
- Binance Futures REST (HMAC)
- Python WebSockets
- dotenv configuration
- CSV audit logging

---

## 📦 Project Structure

```
solana-grid-bot/
├─ bot.py                  # Core logic & event loop
├─ requirements.txt        # Dependencies
├─ .env                    # Secrets & dynamic config
└─ trades.csv              # Runtime trade ledger
```

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
```

> `.gitignore` already protects your secrets.

---

## ▶️ Running the Bot

Dry run (no real money):

```bash
python bot.py
```

Switch to Testnet:

```dotenv
MODE=TESTNET
```

Production:

```dotenv
MODE=LIVE
```

---

## 📊 Sample Runtime Output

```
[WS] Connected
Base price: 190
Filled BUY ladder #3 @ 187.40
Released profit rung #1 @ +$1.02
Open ladders: 3 | Daily spent: $43.00
```

---

## 🛡 Safety Systems

- Max daily exposure guard
- Spread threshold
- Ladder limit
- Clock drift protection
- Dry mode simulation
- Testnet environment

---

## 🧭 Roadmap

- Multi-symbol grid
- Short-grid mirrored logic
- Telegram alerts
- Prometheus metrics dashboard
- Crash-resistant recovery
- Volatility-adaptive spacing

---

## 🤝 Contributions

PRs welcome.  
Please include:

- Sanitized logs
- Steps to reproduce
- Expected vs actual output

---

## 📜 License

MIT — open for commercial & personal use.

---

<div align="center">
<h3>🟣 Automate your profits. Remove your emotions.</h3>
<i>Built by someone who actually trades.</i>
<br><br>
⭐ If this helped you — give it a star!
</div>

<br/><br/>

<div dir="rtl" style="direction: rtl; text-align: right;">

<h2>⚡ בוט גריד אוטומטי למסחר ב-SOL על Binance Futures</h2>
<p><strong>מערכת מסחר אוטומטית</strong> שמבצעת קניות מדורגות בירידות, מממשת רווחים קטנים בעליות, ומאפשרת מסחר רציף ללא מעורבות רגשית — תוך שמירה על גבולות סיכון ברורים.</p>

<h3>🎯 למה דווקא הבוט הזה?</h3>
<ul>
  <li>🔥 רווחים קטנים ומצטברים לאורך היום</li>
  <li>🔒 שליטה חכמה בהון ובלימות סיכון</li>
  <li>🤖 מסחר ללא רגש וללא שחיקה מנטלית</li>
  <li>⚙️ לוגיקה עצמאית לכל שלב (Ladder)</li>
  <li>🧠 התאמה טבעית לתנודתיות בשוק</li>
</ul>

<h3>🧬 איך זה עובד?</h3>
<pre>מחיר יורד → קניית שלב קטן (Ladder)
מחיר עולה → מימוש רווח רק על אותו שלב
…וחוזר בלולאה אוטומטית</pre>

<h3>🛡 מנגנוני הגנה</h3>
<ul>
  <li>🛑 הגבלת חשיפה יומית</li>
  <li>📏 בדיקת מרווח (Spread) לפני ביצוע</li>
  <li>🧱 מספר שלבים מקסימלי</li>
  <li>⏱ בדיקת סטיית זמן לחתימות מדויקות</li>
  <li>🧪 DRY Mode — סימולציה ללא כסף אמיתי</li>
  <li>🧵 Testnet — סביבת ניסוי בחינם</li>
</ul>

<h3>⚠ אזהרת סיכון</h3>
<p>מסחר בחוזים ממונפים עלול לגרום להפסדים משמעותיים. הקוד נועד ללמידה והתנסות — על אחריות המשתמש בלבד.</p>

<p><em>✨ מסחר חכם מתחיל ממערכות שלא מתעייפות.</em></p>

</div>
