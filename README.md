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
# GridBot

A minimal grid trading bot for crypto futures, designed for reliability and safety.

## Overview

The original bot implementation has been reorganized into a clean Python package structure. Key improvements:

- Proper package organization with `src/` layout
- Clear separation of concerns
- Improved state management
- Enhanced price monitoring
- Better configuration handling
- Proper logging and notifications

## Project Structure

```
src/gridbot/
├── __init__.py        # Package initialization
├── __main__.py        # CLI and entry point
├── price.py           # Price stream management
├── broker/            # Exchange interaction
│   ├── binance_connector.py
│   └── notifications.py
├── config/            # Configuration
│   └── settings.py
├── core/              # Core logic
│   ├── grid_logic.py
│   └── utils.py
└── state/             # State persistence
    └── manager.py
```

## Installation

Install in development mode:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Configuration

Create a `.env` file with your settings:

```env
# Trading settings
SYMBOL=SOLUSDT
GRID_STEP_USD=1.0
TAKE_PROFIT_USD=1.0
MAX_LADDERS=20
QTY_PER_LADDER=1.0
MAX_SPREAD_BPS=8
MAX_DAILY_USDT=200

# Exchange settings
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_USE_TESTNET=no
DRY_RUN=yes

# Strategy settings
STRATEGY_SIDE=LONG_ONLY
MARGIN_MODE=ISOLATED

# Optional Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Usage

Run with default settings (dry run mode):
```cmd
python -m gridbot
```

Run with custom settings:
```cmd
python -m gridbot --mid 100 --grid-size 7 --spacing 0.5 --interval 1.0
```

Run in live mode:
```cmd
python -m gridbot --no-dry-run --confirm-live
```

## Safety Features

- Dry run mode by default
- Explicit confirmation needed for live trading
- Position size limits
- Daily spend limits
- Spread monitoring
- Price validation
- Automatic error recovery
- Atomic state persistence

## Development

Suggestions for further development:

1. Add comprehensive test suite
2. Implement connection retries/backoff
3. Add proper rate limiting
4. Enhance logging with file rotation
5. Add metrics collection
6. Create monitoring dashboard
7. Support multiple symbols
8. Add volatility-based grid spacing

## License

MIT License

## Warning

Trading futures contracts carries significant risks. This code is for educational purposes and should be used with caution. Always test thoroughly in dry run and testnet modes before live trading.
