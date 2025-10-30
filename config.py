"""Configuration loader for solana-grid-bot.

Loads values from environment variables when present, otherwise falls back to
`config.example.Config` defaults.
"""
import os
from typing import Optional

try:
    from config_example import config as default_config  # type: ignore
except Exception:
    # If config.example isn't present as module, fallback to simple defaults
    default_config = None


class Config:
    def __init__(self):
        # Credentials
        self.API_KEY: Optional[str] = os.getenv("API_KEY")
        self.API_SECRET: Optional[str] = os.getenv("API_SECRET")

        # Trading params
        self.SYMBOL: str = os.getenv("SYMBOL", "SOL/USDT")
        self.GRID_SIZE: int = int(os.getenv("GRID_SIZE", "10"))
        self.GRID_SPACING: float = float(os.getenv("GRID_SPACING", "1.0"))

        # Paths
        self.STATE_PATH: str = os.getenv("STATE_PATH", "bot_state.json")

        # If defaults exist and an attribute is missing, use them
        if default_config is not None:
            for name in dir(default_config):
                if name.startswith("__"):
                    continue
                if not hasattr(self, name):
                    setattr(self, name, getattr(default_config, name))


config = Config()
