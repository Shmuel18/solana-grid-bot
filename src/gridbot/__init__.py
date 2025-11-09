"""GridBot - A minimal grid trading bot for crypto futures."""

from .broker.binance_connector import Broker as BinanceConnector
from .strategy.grid_logic import compute_grid_levels

__version__ = "0.1.0"