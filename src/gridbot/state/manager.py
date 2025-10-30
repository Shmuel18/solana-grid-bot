"""State management and persistence."""

import datetime
import json
import os

from ..utils.logger import get_logger

logger = get_logger(__name__)
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from ..config.settings import config


@dataclass
class BotState:
    """Trading bot state."""
    base_price: float = 0.0
    positions: List[Dict[str, Any]] = None
    realized_pnl: float = 0.0
    total_buys: int = 0
    total_sells: int = 0
    spent_today: float = 0.0
    spent_date: str = "1970-01-01"

    def __post_init__(self):
        if self.positions is None:
            self.positions = []


def save_state(state_file: str, state: Dict[str, Any]) -> None:
    """Save bot state to file atomically."""
    logger.debug(f"Saving state to {state_file}")
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=4)
    os.replace(tmp, state_file)
    logger.debug("State saved successfully")


def load_state(state_file: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Load bot state from file with defaults."""
    if default is None:
        default = {}
    
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                return default
                
            # Apply defaults for missing keys
            for k, v in default.items():
                data.setdefault(k, v)
                
            return data
                
    except Exception as e:
                    logger.exception("Failed to load state: %s", e)
        
    return default


def get_current_state() -> BotState:
    """Get the current bot state."""
    logger.debug("Loading current bot state")
    raw_state = load_state(config.state_file, default={
        "base_price": 0.0,
        "positions": [],
        "realized_pnl": 0.0,
        "total_buys": 0,
        "total_sells": 0,
        "spent_today": 0.0,
        "spent_date": datetime.datetime.now().strftime("%Y-%m-%d")
    })
    
    return BotState(**raw_state)