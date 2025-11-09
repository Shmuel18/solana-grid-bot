import os
from dataclasses import dataclass, field
from typing import ClassVar
from dotenv import load_dotenv

load_dotenv()

def _parse_bool(env_var: str, default: bool) -> bool:
    val = os.getenv(env_var, str(default)).lower()
    return val in ("1", "true", "yes", "y")

def _parse_int(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, str(default)))
    except ValueError:
        return default

def _parse_float(env_var: str, default: float) -> float:
    try:
        return float(os.getenv(env_var, str(default)))
    except ValueError:
        return default

@dataclass(frozen=True)
class Settings:
    # Trading Parameters
    SYMBOL: str = field(default_factory=lambda: os.getenv("SYMBOL", "SOLUSDT").upper())
    GRID_STEP_USD: float = field(default_factory=lambda: _parse_float("GRID_STEP_USD", 1.0))
    TAKE_PROFIT_USD: float = field(default_factory=lambda: _parse_float("TAKE_PROFIT_USD", 1.0))
    MAX_LADDERS: int = field(default_factory=lambda: _parse_int("MAX_LADDERS", 15))
    QTY_PER_LADDER: float = field(default_factory=lambda: _parse_float("QTY_PER_LADDER", 1.0))
    MAX_SPREAD_BPS: float = field(default_factory=lambda: _parse_float("MAX_SPREAD_BPS", 8.0))
    MAX_OPEN_TRADES: int = field(default_factory=lambda: _parse_int("MAX_OPEN_TRADES", 20))
    MARGIN_MODE: str = field(default_factory=lambda: os.getenv("MARGIN_MODE", "CROSSED").upper()) # ISOLATED/CROSSED

    # API & Environment
    API_KEY: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    API_SECRET: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    USE_TESTNET: bool = field(default_factory=lambda: _parse_bool("USE_TESTNET", False))
    DRY_RUN: bool = field(default_factory=lambda: _parse_bool("DRY_RUN", True))
    COPY_TRADE_ASSUMED_BALANCE: float = field(default_factory=lambda: _parse_float("COPY_TRADE_ASSUMED_BALANCE", 500.0))

    # Fees & Budget
    TAKER_FEE: float = field(default_factory=lambda: _parse_float("TAKER_FEE", 0.0005))
    MAX_DAILY_USDT: float = field(default_factory=lambda: _parse_float("MAX_DAILY_USDT", 10000.0))
    AUTO_FEE: bool = field(default_factory=lambda: _parse_bool("AUTO_FEE", False))

    # State & Logging
    CSV_FILE: str = field(default_factory=lambda: os.getenv("CSV_FILE", "trades.csv"))
    STATE_FILE: str = field(default_factory=lambda: os.getenv("STATE_FILE", "bot_state.json"))
    SESSION_TAG_ENV: str = field(default_factory=lambda: os.getenv("SESSION_TAG", "").strip())
    DEBUG_VERBOSE: bool = field(default_factory=lambda: _parse_bool("DEBUG_VERBOSE", True))
    INTERVAL_STATUS_SEC: float = field(default_factory=lambda: _parse_float("INTERVAL_STATUS_SEC", 1.5))

    # Cooldowns & Refill
    DUPLICATE_COOLDOWN_SEC: float = field(default_factory=lambda: _parse_float("DUPLICATE_COOLDOWN_SEC", 90.0))
    INSTANT_TP_REFILL: bool = field(default_factory=lambda: _parse_bool("INSTANT_TP_REFILL", False))
    SUPPRESS_SEC_AFTER_CANCEL: float = field(default_factory=lambda: _parse_float("SUPPRESS_SEC_AFTER_CANCEL", 8.0))
    SUPPRESS_SEC_ON_UNKNOWN: float = field(default_factory=lambda: _parse_float("SUPPRESS_SEC_ON_UNKNOWN", 3.0))
    PENDING_LOCK_MAX_SEC: float = field(default_factory=lambda: _parse_float("PENDING_LOCK_MAX_SEC", 3.0))

    # Trailing
    TRAIL_UP: bool = field(default_factory=lambda: _parse_bool("TRAIL_UP", True))
    TRAIL_TRIGGER_STEPS: int = field(default_factory=lambda: max(1, _parse_int("TRAIL_TRIGGER_STEPS", 1)))
    TRAIL_MAX_CANCEL_PER_REANCHOR: int = field(default_factory=lambda: _parse_int("TRAIL_MAX_CANCEL_PER_REANCHOR", 100))

    # Price Refresh
    PRICE_REFRESH_SEC: float = field(default_factory=lambda: _parse_float("PRICE_REFRESH_SEC", 0.5))

    # Telegram
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    # Derived properties (read-only)
    FUTURES_HTTP_BASE: ClassVar[str]
    FUTURES_BASE_URL: ClassVar[str]
    FUTURES_ACCOUNT_URL: ClassVar[str]

    def __post_init__(self):
        # Calculate derived properties and set them on the instance (using object.__setattr__ for frozen dataclass)
        is_testnet_fut = self.USE_TESTNET
        http_base = "https://testnet.binancefuture.com" if is_testnet_fut else "https://fapi.binance.com"
        base_url = f"{http_base}/fapi/v1"
        account_url = f"{http_base}/fapi/v2"

        object.__setattr__(self, 'FUTURES_HTTP_BASE', http_base)
        object.__setattr__(self, 'FUTURES_BASE_URL', base_url)
        object.__setattr__(self, 'FUTURES_ACCOUNT_URL', account_url)

def load_settings() -> Settings:
    return Settings()