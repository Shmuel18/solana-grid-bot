"""Example configuration values for solana-grid-bot.

This file is intended as a local example / template. Do NOT store real API
secrets here. Use environment variables or a secrets manager in production.
"""
from dataclasses import dataclass


@dataclass
class Config:
    API_KEY: str = ""
    API_SECRET: str = ""

    SYMBOL: str = "SOL/USDT"
    GRID_SIZE: int = 10
    GRID_SPACING: float = 1.0

    STATE_PATH: str = "bot_state.json"


config = Config()
