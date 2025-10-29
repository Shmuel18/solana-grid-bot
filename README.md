מעולה. כפי שהומלץ בביקורת, הנה קובץ ה-`README.md` המתוקן.

השינויים העיקריים הם: עדכון הכותרות והפיצ'רים לשקף את התמיכה ב-**Binance Futures / Copy Trading**, הוספת הערה על השימוש בחתימת **HMAC** ידנית, והוספת המשתנה החדש לקובץ ה-`.env`.

````markdown
# 💰 Solana Grid Bot (Futures Edition)

### A simple and efficient DCA-style grid trading bot for SOL/USDT, fully adapted for **Binance Futures / Copy Trading Lead Accounts**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Binance API](https://img.shields.io/badge/API-Binance%20Futures-yellow)
![Status](https://img.shields.io/badge/Mode-LIVE%20%7C%20Futures-red)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 🧠 Overview

This bot executes **grid-style DCA trades** on the `SOL/USDT` pair.
It is configured specifically to operate as a **Lead Trader** on **Binance UM Futures** (Unified Margin) / **Copy Trading** accounts.
It continuously listens to real-time prices via **Binance WebSocket**, and automatically places **BUY** and **SELL** orders at fixed dollar intervals using direct, signed HTTP requests.

✅ Designed for _stable, predictable, automated trading_
✅ **Fully compatible with Copy Trading API keys**
✅ Supports **dry-run**, **testnet**, and **live** trading modes
✅ Logs trades to a CSV file
✅ Simple configuration via `.env` file

---

## ⚙️ Features

| Feature                      | Description                                                                                                       |
| :--------------------------- | :---------------------------------------------------------------------------------------------------------------- |
| **🚀 Futures/UM Support**    | **Full support for Binance Futures API** (required for Lead/Copy Trading).                                        |
| **🔐 Custom HMAC Signature** | Uses direct, manually signed HTTP requests to bypass problematic library errors and ensure proper authentication. |
| **🛠️ Position Side Fix**     | Includes `positionSide='LONG'` and `reduceOnly='true'` parameters for correct order execution on Futures (UM).    |
| 🔁 Grid Logic                | Places laddered buy/sell orders every fixed dollar step                                                           |
| 💸 Take Profit               | Sells automatically at a defined profit level                                                                     |
| 🧩 Real-Time Updates         | Uses Binance WebSocket for instant price tracking                                                                 |
| 🧾 CSV Logging               | Saves all trades with timestamps                                                                                  |
| ⚙️ Configurable              | Edit `.env` to control bot parameters                                                                             |
| 🧱 DRY Mode                  | Safe simulation — no real money involved                                                                          |

---

## 🧰 Installation

### 1️⃣ Clone the repository

```bash
git clone [https://github.com/Shmuel18/solana-grid-bot.git](https://github.com/Shmuel18/solana-grid-bot.git)
cd solana-grid-bot
```
````

### 2️⃣ Create a virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
# source .venv/bin/activate   # On Mac/Linux
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The bot uses the `requests` library for market orders. The `binance-connector` is primarily used only for initial exchange information retrieval.

---

## 🔐 Configuration (`.env`)

Create a file named `.env` in the project root and fill in your settings:

```bash
# Binance API keys (must be Futures/Copy Trading API keys)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here

# Bot parameters
SYMBOL=SOLUSDT
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200.0 # Maximum total capital to deploy in 24h
CSV_FILE=trades.csv

# If API key has no permission to check balance (Error 401),
# this amount is used for a soft check before placing orders.
COPY_TRADE_ASSUMED_BALANCE=500.0

# Mode: DRY / TESTNET / LIVE
MODE=LIVE
```

> ⚠️ Keep `.env` private — it contains your API keys\!
> The `.gitignore` already excludes it from GitHub.

---

## ▶️ Running the Bot

### Dry run (simulation)

```bash
python bot.py
```

### Live mode (real Binance trading on Futures)

Change in `.env`:

```
MODE=LIVE
```

Then run again:

```bash
python bot.py
```

---

## 📊 Example Output

```
Starting SOL bot on SOLUSDT | Mode=LIVE
Broker ready.
Base price (rounded): 199

[WS] Connected.

[ENTER LIVE] qty=0.1 @ ~198.6800 | open=1 | spread=0.50bps | orderId=164579406034
Mid=198.6750 | Bid=198.6700 Ask=198.6800 | Spread=0.50bps | Base=199 | Open=1 | B
...
```

---

## 🧱 Project Structure

```
solana-grid-bot/
│
├── bot.py              # Main bot logic (now with custom Futures API calls)
├── .env                # Environment configuration (ignored in git)
├── .gitignore          # Ignore env/venv/logs/trades
├── requirements.txt    # Python dependencies
├── README.md           # Project documentation (this file)
└── trades.csv          # Trade history (auto-generated)
```

---

## 🧩 Technologies

- **Python 3.10+**
- **Direct Requests & HMAC Signature (for Futures API)**
- **Binance Connector (for exchange info only)**
- **dotenv**
- **requests**
- **websocket-client**

---

## 🧠 Next Steps

- **Safety & Persistence:** Implement position/state saving (serialization) to resume trading after a crash.
- Add Telegram alerts 📲
- Add dashboard for live tracking 📈
- Add strategy switching (short side support)

---

## 🪪 License

This project is licensed under the **MIT License** — feel free to use and modify.

---

### 💬 Created with ❤️ by [Shmuel18](https://github.com/Shmuel18)

---

---

\<div dir="rtl"\>

## 💰 בוט גריד לסולאנה (גרסת Futures)

### בוט מסחר אוטומטי חכם בשיטת DCA עבור SOL/USDT, מותאם לחשבונות **Binance Futures / Copy Trading Lead**

---

## 🧠 סקירה

הבוט מבצע עסקאות קנייה ומכירה מדורגות (Grid) על מטבע **SOL/USDT**.
הוא מוגדר במיוחד לעבודה כ-**Lead Trader** בחשבונות **Binance Futures UM / Copy Trading**.
הוא מאזין בזמן אמת למחירים דרך **Binance WebSocket**, ומבצע קניות ומכירות באופן אוטומטי במרווחי דולר קבועים באמצעות בקשות HTTP חתומות וישירות.

✅ מסחר אוטומטי יציב וצפוי
✅ **תואם מלא למפתחות Copy Trading API**
✅ כולל מצב **סימולציה (Dry Run)** ו־**מסחר אמיתי (Live)**
✅ רישום עסקאות אוטומטי ל־CSV
✅ קובץ הגדרות פשוט לשינוי (`.env`)

---

## ⚙️ תכונות עיקריות

| תכונה                      | תיאור                                                                                      |
| :------------------------- | :----------------------------------------------------------------------------------------- |
| **🚀 תמיכת Futures/UM**    | **תמיכה מלאה ב-Binance Futures API** (נדרש ל-Lead/Copy Trading).                           |
| **🔐 חתימת HMAC מותאמת**   | משתמש בבקשות HTTP ישירות וחתומות ידנית כדי לעקוף שגיאות תוכנה ולהבטיח אימות נכון.          |
| **🛠️ תיקון Position Side** | כולל את הפרמטרים `positionSide='LONG'` ו-`reduceOnly='true'` לביצוע פקודות תקין ב-Futures. |
| 🔁 גריד לוגי               | פקודות קנייה/מכירה כל דולר אחד                                                             |
| 💸 רווח אוטומטי            | מוכר באופן אוטומטי ברווח שנקבע                                                             |
| 🧩 נתונים בזמן אמת         | מבוסס WebSocket לעדכון מיידי                                                               |
| 🧾 תיעוד עסקאות            | שומר כל עסקה עם תאריך ושעה                                                                 |
| ⚙️ התאמה אישית             | שליטה מלאה בפרמטרים דרך `.env`                                                             |
| 🧱 מצב יבש (Dry)           | מאפשר בדיקה ללא סיכון כספי                                                                 |

---

## 🧰 התקנה

### 1️⃣ שכפל את הריפו

```bash
git clone [https://github.com/Shmuel18/solana-grid-bot.git](https://github.com/Shmuel18/solana-grid-bot.git)
cd solana-grid-bot
```

### 2️⃣ צור סביבת פיתוח

```bash
python -m venv .venv
.\.venv\Scripts\activate   # ב-Windows
# source .venv/bin/activate   # ב-Linux/Mac
```

### 3️⃣ התקן את כל התלויות

```bash
pip install -r requirements.txt
```

---

## 🔐 קובץ ההגדרות (`.env`)

צור קובץ בשם `.env` בתיקייה הראשית והכנס בו את ההגדרות שלך:

```bash
# מפתחות Binance API (חייבים להיות מפתחות Futures/Copy Trading)
BINANCE_API_KEY=המפתח_שלך
BINANCE_API_SECRET=הסוד_שלך

# פרמטרים של הבוט
SYMBOL=SOLUSDT
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200.0 # סך ההון המקסימלי לשימוש ב-24 שעות
CSV_FILE=trades.csv

# אם למפתח ה-API אין הרשאה לבדוק יתרה (שגיאה 401), סכום זה ישמש לבדיקה רכה לפני ביצוע פקודה.
COPY_TRADE_ASSUMED_BALANCE=500.0

# מצב: DRY / TESTNET / LIVE
MODE=LIVE
```

⚠️ **לעולם אל תעלה את `.env` לגיטהאב** — הוא מוחרג אוטומטית ב־`.gitignore`.

---

## ▶️ הפעלת הבוט

### מצב בדיקה (Dry Run)

```bash
python bot.py
```

### מצב מסחר אמיתי (ב-Futures)

ערוך את `.env`:

```
MODE=LIVE
```

והפעל שוב:

```bash
python bot.py
```

---

## 📊 דוגמה לפלט

```
Starting SOL bot on SOLUSDT | Mode=LIVE
Broker ready.
Base price (rounded): 199

[WS] Connected.

[ENTER LIVE] qty=0.1 @ ~198.6800 | open=1 | spread=0.50bps | orderId=164579406034
...
```

---

## 📁 מבנה הפרויקט

```
solana-grid-bot/
├── bot.py              # קובץ הבוט הראשי (כעת עם קריאות API ידניות ל-Futures)
├── .env                # קובץ הגדרות (מוחרג מהגיט)
├── .gitignore          # קובץ החרגות
├── requirements.txt    # תלויות (ספריות נדרשות)
├── README.md           # מדריך זה
└── trades.csv          # תיעוד העסקאות
```

---

## 🧩 טכנולוגיות

- Python 3.10+
- Direct Requests & HMAC Signature (עבור Futures API)
- Binance Connector (משמש רק לשליפת מידע על הבורסה)
- dotenv
- requests
- websocket-client

---

## 🧠 תוכניות עתידיות

- **בטיחות והתמדה:** הטמעת מנגנון שמירת מצב (Serialization) לחידוש מסחר לאחר קריסה.
- שליחת התראות לטלגרם 📲
- לוח מעקב בזמן אמת 📈
- תמיכה במסחר Short

---

## 🪪 רישיון

הפרויקט תחת רישיון **MIT** — מותר להשתמש ולשנות בחופשיות.

---

### 💬 נבנה באהבה ❤️ על ידי [Shmuel18](https://github.com/Shmuel18)

\</div\>

```

```
