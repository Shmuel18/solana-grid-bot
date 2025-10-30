"""Configuration management for GridBot."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _validate_strategy_side(side: str) -> str:
    """Validate and normalize strategy side."""
    if side not in ["LONG_ONLY", "SHORT_ONLY"]:
        logging.warning("Invalid STRATEGY_SIDE '%s', defaulting to LONG_ONLY", side)
        return "LONG_ONLY"
    return side


def _validate_margin_mode(mode: str) -> str:
    """Validate and normalize margin mode."""
    if mode not in ["CROSSED", "ISOLATED"]:
        logging.warning("Invalid MARGIN_MODE '%s', defaulting to ISOLATED", mode)
        return "ISOLATED"
    return mode


@dataclass
class BotConfig:
    """Bot configuration settings."""
    
    # Trading settings
    symbol: str = os.getenv("SYMBOL", "SOLUSDT").upper()
    grid_step_usd: float = float(os.getenv("GRID_STEP_USD", "1.0"))
    take_profit_usd: float = float(os.getenv("TAKE_PROFIT_USD", "1.0"))
    max_ladders: int = int(os.getenv("MAX_LADDERS", "20"))
    qty_per_ladder: float = float(os.getenv("QTY_PER_LADDER", "1.0"))
    max_spread_bps: float = float(os.getenv("MAX_SPREAD_BPS", "8"))
    max_daily_usdt: float = float(os.getenv("MAX_DAILY_USDT", "200"))
    taker_fee: float = float(os.getenv("TAKER_FEE", "0.0005"))

    # Files
    csv_file: str = os.getenv("CSV_FILE", "trades.csv")
    state_file: str = os.getenv("STATE_FILE", "bot_state.json")

    # Exchange settings  
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    use_testnet: bool = os.getenv("BINANCE_USE_TESTNET", "no").lower() == "yes"
    copy_trade_balance: float = float(os.getenv("COPY_TRADE_ASSUMED_BALANCE", "500.0"))

    # Strategy settings
    strategy_side: str = _validate_strategy_side(os.getenv("STRATEGY_SIDE", "LONG_ONLY").upper())
    margin_mode: str = _validate_margin_mode(os.getenv("MARGIN_MODE", "ISOLATED").upper())
    desired_position_mode: Optional[str] = os.getenv("DESIRED_POSITION_MODE", "").upper() or None
    dry_run: bool = os.getenv("DRY_RUN", "yes").lower() == "yes"

    # Notification settings
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Connection settings
    ping_interval: float = float(os.getenv("PING_INTERVAL", "10.0"))
    ping_timeout: float = float(os.getenv("PING_TIMEOUT", "5.0"))
    reconnect_min: float = 1.0
    reconnect_max: float = 30.0
    price_refresh_sec: float = float(os.getenv("PRICE_REFRESH_SEC", "0.5"))
    stale_ws_sec: float = float(os.getenv("STALE_WS_SEC", "5"))
    interval_status_sec: float = float(os.getenv("INTERVAL_STATUS_SEC", "1.5"))

    @property
    def stream_symbol(self) -> str:
        """Get WebSocket stream symbol in lowercase."""
        return self.symbol.lower()

    @property
    def is_testnet_futures(self) -> bool:
        """Check if using futures testnet."""
        return self.use_testnet

    @property
    def futures_http_base(self) -> str:
        """Get futures base HTTP URL."""
        return "https://testnet.binancefuture.com" if self.is_testnet_futures else "https://fapi.binance.com"

    @property  
    def futures_base_url(self) -> str:
        """Get futures API base URL."""
        return f"{self.futures_http_base}/fapi/v1"

    @property
    def futures_account_url(self) -> str:
        """Get futures account API URL."""
        return f"{self.futures_http_base}/fapi/v2"

    @property
    def ws_host(self) -> str:
        """Get WebSocket host."""
        return "stream.binancefuture.com" if self.is_testnet_futures else "fstream.binance.com"

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL for bookTicker."""
        return f"wss://{self.ws_host}/ws/{self.stream_symbol}@bookTicker"

# Global config instance
config = BotConfig()