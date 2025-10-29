---

## 🇬🇧 README.md (English)

```markdown
# ✨ Solana Grid Bot (Futures Edition) ✨

**Full-stack automation meets smart trading.**  
A clean, efficient DCA-grid bot designed for **SOL/USDT** on Binance UM Futures, ready for **Lead Copy-Trading** deployment.

---

## 👤 About Me

Hi, I’m Shmuel — a driven crypto-trader & developer from Tel Aviv, blending code with capital-markets smarts.  
I build tools that run while I sleep, so my money works—**even when I don’t**.  
I’m passionate about: automation · risk-control · elegant code.

---

## 🧰 Tech Stack

**Languages & Platforms**

- Python 3.10+
- Binance API (UM Futures)

**Tools & Libraries**

- WebSockets for live feeds
- HMAC & REST for order management
- CSV logging + lightweight orchestration

---

## 🚀 Featured Project: Solana Grid Bot

This project implements:

- Laddered buy orders at fixed USD intervals.
- Per-rung take-profit closes for swift gains.
- Fully configurable via `.env`.
- Supports DRY-run, TESTNET and LIVE modes.

---

## ⚡ Highlights

- **Symbol:** SOLUSDT
- **Mode options:** DRY · TESTNET · LIVE
- **Key safety features:** max daily deployable capital · spread threshold protection · manual risk cap
- **Copy-Trading friendly:** built to lead, share signals, or auto-execute.

---

## 📦 Project Structure

```

solana-grid-bot/
├── bot.py
├── requirements.txt
├── .env                # config & secrets (git-ignored)
├── trades.csv          # runtime log
└── README.md

```

---

## 🔧 Getting Started

Clone and setup:

```bash
git clone https://github.com/Shmuel18/solana-grid-bot.git
cd solana-grid-bot
pip install -r requirements.txt
```

(Optional) Virtual environment:

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

Create `.env`:

```dotenv
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

SYMBOL=SOLUSDT
MODE=DRY              # DRY | TESTNET | LIVE
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

Run the bot:

```bash
python bot.py
```

Switch `MODE` to `TESTNET` or `LIVE` as needed.

---

## 🛡️ Safety & Risk Management

Trading futures is inherently risky.
Before switching to LIVE:

- Familiarize with margin, liquidation, leverage.
- Align `MAX_LADDERS × QTY_PER_LADDER` to available balance.
- Confirm `GRID_STEP_USD` and `TAKE_PROFIT_USD` match symbol volatility.
- Use `MAX_DAILY_USDT` as hard stop for day-risk.
- Test extensively in DRY and TESTNET modes.

---

## ❓ FAQ

**Can I change the symbol?**
Yes — update `SYMBOL`, review min qty/step filters.

**Does it handle shorts?**
Not yet — currently LONG only.

**Is testnet safe?**
Yes — no real funds are at risk.

---

## 🗺️ Roadmap

- Multi-symbol support
- Short grid mode
- Adaptive step sizing by volatility
- Telegram alerts & webhook integration
- Dashboard with metrics & live view
- Recovery and crash-resilience mode

---

## 🤝 Contribute

Pull requests and feedback are welcome.
Please include:

- Reproduction steps
- Console logs (sanitized)
- Expected vs actual behaviour

---

## 📜 License

MIT — free for personal or commercial use.

> ⚠️ _Not financial advice. Trading crypto derivatives carries a risk of loss._

````

---

## 🇮🇱 README.he.md (עברית)

```markdown
<div dir="rtl">

# ✨ בוט גריד לסולאנה (גרסת Futures) ✨

**אוטומציה מלאה + מסחר חכם.**
בוט DCA-גריד אלגנטי ומבוסס קוד ל־SOL/USDT על Binance UM Futures, עם תמיכה מובנית ב-Lead Copy-Trading.

---

## 👤 אודותי

שלום, אני שמואל — סוחר קריפטו ומפתח מתל-אביב, שמחבר בין קוד לבין שוקי הון.
אני יוצר כלים שרצים עבורך גם כשאתה ישן — **כדי שהכסף שלך יעבוד, גם כשאתה לא**.
תחומי התשוקה שלי: אוטומציה · שליטה בסיכון · קוד נקי ומדויק.

---

## 🧰 טכנולוגיות

**שפות ופלטפורמות**
- Python 3.10 ומעלה
- API של Binance Futures (UM)

**כלים וספריות**
- WebSocket לקבלת מחירים בזמן אמת
- HMAC + REST לניהול הזמנות
- רישום CSV + סקריפט פשוט לתפעול

---

## 🚀 פרויקט נבחר: בוט גריד לסולאנה

הפרויקט כולל:
- הזמנת קניות מדורגות בכל ירידת USD קבועה.
- סגירת רווח מהירה בכל שלב בסולם.
- התצורה דרך קובץ `.env`.
- מצבי DRY ​| TESTNET ​| LIVE.

---

## ⚡ נקודות בולטות

- **מטבע יעד:** SOLUSDT
- **מצבי הרצה:** DRY · TESTNET · LIVE
- **מאפייני ביטחון מרכזיים:** הגבלת הון יומית · ספירת ספראד (bps) · בקרה ידנית
- **Friendly Copy-Trading:** מיועד להובלה או לשיתוף אותות.

---

## 📁 מבנה הפרויקט

````

solana-grid-bot/
├── bot.py
├── requirements.txt
├── .env # קובץ הגדרות וסודות (לא ב-git)
├── trades.csv # לוג הרצה בזמן אמת
└── README.md

````

---

## 🔧 התחלת עבודה

העתק והריץ:
```bash
git clone https://github.com/Shmuel18/solana-grid-bot.git
cd solana-grid-bot
pip install -r requirements.txt
````

(אופציונלי) סביבה וירטואלית:

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

יצירת קובץ `.env`:

```dotenv
BINANCE_API_KEY=המפתח_שלך
BINANCE_API_SECRET=הסוד_שלך

SYMBOL=SOLUSDT
MODE=DRY              # DRY | TESTNET | LIVE
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

להרצה:

```bash
python bot.py
```

לשינוי ל-TESTNET או LIVE — ערוך את `MODE`.

---

## 🛡️ בדיקות בטיחות

נסחרים במכשירים ממונפים? זה לא בדיחה.
לפני מצב LIVE:

- הבן עומק של מינוף, ליקווידציה ומצב שוק.
- ודא ש־`MAX_LADDERS × QTY_PER_LADDER` מתאים לאיזון שלך.
- התאמן בסביבת DRY וב־TESTNET עד שאתה מרגיש נוח.
- קבע תקרה יומית (`MAX_DAILY_USDT`) כהגנת סיכון.
- ודא שהשעון במחשב מסונכרן.

---

## 🐛 תקלות נפוצות

| תקלה נפוצה                   | פתרון מוצע                                |
| ---------------------------- | ----------------------------------------- |
| שגיאת Timestamp / recvWindow | סנכרן זמן המערכת                          |
| הזמנות לא מתבצעות            | הגדל `MAX_SPREAD_BPS` או תקן גריד         |
| “Insufficient margin” במימון | הקטן את `MAX_LADDERS` או `QTY_PER_LADDER` |
| מפתח Copy-Trading מוגבל      | השתמש ב־`COPY_TRADE_ASSUMED_BALANCE`      |

---

## 🧠 שאלות נפוצות

**האם אפשר לשנות מטבע?**
כן — שנה את `SYMBOL` אך התאמה של פרמטרים חיווי נדרשת.

**תומך בשורט?**
כרגע לא — בפיתוח.

**האם TESTNET בטוח?**
כן — ללא סיכון כספי אמיתי.

---

## 🗺️ מפת דרכים (Roadmap)

- תמיכה במספר מטבעות בו-זמנית
- גריד שורט (Short-grid)
- התאמת שלבים דינמית לפי וולטיליות
- התראות דרך Telegram / Webhook
- Dashboard גרפי / Metrics
- מצב התאוששות לאחר כשל (Crash-Recovery)

---

## 🤝 תרומה

ברוכים הבאים — PRים ו-Issues מתקבלים בברכה.
בבקשה כלל:

- תחביר לשחזור
- לוגים (ללא מפתחות)
- תיאור השוני בין צפוי לבין ממשי

---

## 📜 רישיון

MIT — שימוש חופשי (בהתאם)

> ⚠️ _הודעת סיכון:_
> הפרויקט למטרות לימוד בלבד. עסקה בקריפטו ממונפת כרוכה בסיכון גבוה במיוחד — כל הכסף עלול ללכת!

</div>
```

---
