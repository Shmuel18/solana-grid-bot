"""GridBot - A minimal grid trading bot for crypto futures."""

from .broker import BinanceConnector
from .core.grid_logic import compute_grid_levels
from .core.utils import append_csv_row
from .state.manager import load_state, save_state

__version__ = "0.1.0"