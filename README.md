````markdown
# 💰 Solana Grid Bot

### A simple and efficient DCA-style grid trading bot for SOL/USDT

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Binance API](https://img.shields.io/badge/API-Binance-yellow)
![Status](https://img.shields.io/badge/Mode-DRY%20RUN%20%7C%20LIVE-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 🧠 Overview

This bot executes **grid-style DCA trades** on the `SOL/USDT` pair.  
It continuously listens to real-time prices via **Binance WebSocket**,  
and automatically places **buy** and **sell** orders at fixed dollar intervals.

✅ Designed for _stable, predictable, automated trading_  
✅ Supports **dry-run**, **testnet**, and **live** trading modes  
✅ Logs trades to a CSV file  
✅ Simple configuration via `.env` file

---

## ⚙️ Features

| Feature              | Description                                             |
| -------------------- | ------------------------------------------------------- |
| 🔁 Grid Logic        | Places laddered buy/sell orders every fixed dollar step |
| 💸 Take Profit       | Sells automatically at a defined profit level           |
| 🧩 Real-Time Updates | Uses Binance WebSocket for instant price tracking       |
| 🧾 CSV Logging       | Saves all trades with timestamps                        |
| ⚙️ Configurable      | Edit `.env` to control bot parameters                   |
| 🧱 DRY Mode          | Safe simulation — no real money involved                |

---

## 🧰 Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/Shmuel18/solana-grid-bot.git
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

---

## 🔐 Configuration (`.env`)

Create a file named `.env` in the project root and fill in your settings:

```bash
# Binance API keys
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
CSV_FILE=trades.csv

# Mode: DRY / TESTNET / LIVE
MODE=DRY
```

> ⚠️ Keep `.env` private — it contains your API keys!
> The `.gitignore` already excludes it from GitHub.

---

## ▶️ Running the Bot

### Dry run (simulation)

```bash
python bot.py
```

### Live mode (real Binance trading)

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
Starting SOL bot on SOLUSDT | Mode=DRY
Mid=202.25 | Bid=202.20 Ask=202.30 | Spread=0.5bps | Base=203 | Open=1 | Buys=1 Sells=0 | Realized=$0.00
Mid=202.10 | Bid=202.05 Ask=202.15 | Spread=0.5bps | Ladder=Buy#2 @201
...
Bye!
```

---

## 🧱 Project Structure

```
solana-grid-bot/
│
├── bot.py              # Main bot logic
├── .env                # Environment configuration (ignored in git)
├── .gitignore          # Ignore env/venv/logs/trades
├── requirements.txt    # Python dependencies
├── README.md           # Project documentation
└── trades.csv          # Trade history (auto-generated)
```

---

## 🧩 Technologies

- **Python 3.10+**
- **Binance Connector (REST + WebSocket)**
- **dotenv**
- **requests**
- **websocket-client**

---

## 🧠 Next Steps

- Add Telegram alerts 📲
- Add dashboard for live tracking 📈
- Add strategy switching (long / short / adaptive)

---

## 🪪 License

This project is licensed under the **MIT License** — feel free to use and modify.

---

### 💬 Created with ❤️ by [Shmuel18](https://github.com/Shmuel18)

---

---

# 🇮🇱 גרסה בעברית (תמיכה מלאה מימין לשמאל)

<div dir="rtl">

## 💰 בוט גריד לסולאנה

### בוט מסחר אוטומטי חכם בשיטת DCA עבור SOL/USDT

---

## 🧠 סקירה

הבוט מבצע עסקאות קנייה ומכירה מדורגות (Grid) על מטבע **SOL/USDT**.
הוא מאזין בזמן אמת למחירים דרך **Binance WebSocket**,
ומבצע קניות ומכירות באופן אוטומטי כל דולר אחד (או לפי הגדרה שלך).

✅ מסחר אוטומטי יציב וצפוי
✅ כולל מצב **סימולציה (Dry Run)** ו־**מסחר אמיתי (Live)**
✅ רישום עסקאות אוטומטי ל־CSV
✅ קובץ הגדרות פשוט לשינוי (`.env`)

---

## ⚙️ תכונות עיקריות

| תכונה              | תיאור                          |
| ------------------ | ------------------------------ |
| 🔁 גריד לוגי       | פקודות קנייה/מכירה כל דולר אחד |
| 💸 רווח אוטומטי    | מוכר באופן אוטומטי ברווח שנקבע |
| 🧩 נתונים בזמן אמת | מבוסס WebSocket לעדכון מיידי   |
| 🧾 תיעוד עסקאות    | שומר כל עסקה עם תאריך ושעה     |
| ⚙️ התאמה אישית     | שליטה מלאה בפרמטרים דרך `.env` |
| 🧱 מצב יבש (Dry)   | מאפשר בדיקה ללא סיכון כספי     |

---

## 🧰 התקנה

### 1️⃣ שכפל את הריפו

```bash
git clone https://github.com/Shmuel18/solana-grid-bot.git
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
BINANCE_API_KEY=המפתח_שלך
BINANCE_API_SECRET=הסוד_שלך

SYMBOL=SOLUSDT
INTERVAL_STATUS_SEC=1.5
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
CSV_FILE=trades.csv

MODE=DRY
```

⚠️ **לעולם אל תעלה את `.env` לגיטהאב** — הוא מוחרג אוטומטית ב־`.gitignore`.

---

## ▶️ הפעלת הבוט

### מצב בדיקה (Dry Run)

```bash
python bot.py
```

### מצב מסחר אמיתי

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
Starting SOL bot on SOLUSDT | Mode=DRY
Mid=202.25 | Bid=202.20 Ask=202.30 | Spread=0.5bps | Base=203 | Open=1 | Buys=1 Sells=0 | Realized=$0.00
...
Bye!
```

---

## 📁 מבנה הפרויקט

```
solana-grid-bot/
├── bot.py              # קובץ הבוט הראשי
├── .env                # קובץ הגדרות (מוחרג מהגיט)
├── .gitignore          # קובץ החרגות
├── requirements.txt    # תלויות (ספריות נדרשות)
├── README.md           # מדריך זה
└── trades.csv          # תיעוד העסקאות
```

---

## 🧩 טכנולוגיות

- Python 3.10+
- Binance Connector (REST + WebSocket)
- dotenv
- requests
- websocket-client

---

## 🧠 תוכניות עתידיות

- שליחת התראות לטלגרם 📲
- לוח מעקב בזמן אמת 📈
- מעבר דינמי בין אסטרטגיות (לונג / שורט)

---

## 🪪 רישיון

הפרויקט תחת רישיון **MIT** — מותר להשתמש ולשנות בחופשיות.

---

### 💬 נבנה באהבה ❤️ על ידי [Shmuel18](https://github.com/Shmuel18)

</div>
```
