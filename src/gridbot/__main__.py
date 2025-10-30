"""Command line interface and bot entry point."""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from typing import Optional

from . import BinanceConnector
from .broker.notifications import send_telegram_message
from .config.settings import config
from .core.grid_logic import align_to_grid, compute_grid_levels
from .core.utils import init_csv, init_logging, log_trade
from .price import PriceManager
from .state.manager import get_current_state, save_state


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="GridBot (safe default: dry-run)")
    p.add_argument(
        "--symbol",
        default=os.getenv("SYMBOL", "SOLUSDT"),
        help="Symbol (e.g. SOLUSDT)"
    )
    p.add_argument(
        "--mid",
        type=float,
        default=float(os.getenv("DEMO_MID", "100.0")),
        help="Mid price to construct grid around"
    )
    p.add_argument(
        "--grid-size",
        type=int,
        default=int(os.getenv("GRID_SIZE", "5")),
        help="Number of grid levels"
    )
    p.add_argument(
        "--spacing",
        type=float,
        default=float(os.getenv("GRID_SPACING", "1.0")),
        help="Spacing between grid levels"
    )
    p.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("POLL_INTERVAL", "2.0")),
        help="Polling interval seconds"
    )
    p.add_argument(
        "--state",
        default=os.getenv("STATE_PATH", "bot_state.json"),
        help="Path to state file"
    )
    p.add_argument(
        "--qty-per-order",
        type=float,
        default=float(os.getenv("QTY_PER_LADDER", "1.0")),
        help="Quantity per order"
    )
    p.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Disable dry-run and allow real API calls if credentials available"
    )
    p.add_argument(
        "--testnet",
        action="store_true",
        help="Use Binance Futures testnet base URLs (only relevant when not dry-run)"
    )
    p.add_argument(
        "--confirm-live",
        dest="confirm_live",
        action="store_true",
        help="Explicit confirmation to allow live trading when dry-run is disabled"
    )
    p.set_defaults(dry_run=True, confirm_live=False)
    return p.parse_args()


class GridBot:
    """Grid trading bot implementation."""

    def __init__(self, args: argparse.Namespace):
        """Initialize bot with arguments."""
        self.args = args
        self.stop_evt = threading.Event()
        self.state = get_current_state()
        self.connector = BinanceConnector()
        self.grid = compute_grid_levels(args.mid, args.grid_size, args.spacing)
        self.price_manager = PriceManager(args.symbol)

    def initialize(self) -> None:
        """Initialize trading system."""
        if not self.state.positions:
            try:
                ticker = self.connector.get_ticker(self.args.symbol)
                mid = ticker.get("mid", (ticker.get("bid", 0.0) + ticker.get("ask", 0.0)) / 2.0)
                self.state.base_price = align_to_grid(mid, config.grid_step_usd, config.strategy_side)
            except Exception as e:
                logging.warning(f"Initial ticker fetch failed, using default: {e}")
                self.state.base_price = align_to_grid(200.0, config.grid_step_usd, config.strategy_side)

        save_state(self.args.state, vars(self.state))
        init_csv()

    def process_grid(self, bid: float, ask: float, mid: float) -> None:
        """Process grid logic for current prices."""
        is_long_strategy = (config.strategy_side == "LONG_ONLY")

        # Entry logic
        if is_long_strategy and mid < self.state.base_price:
            self._maybe_enter(bid, ask)
        elif not is_long_strategy and mid > self.state.base_price:
            self._maybe_enter(bid, ask)

        # Exit logic
        if self.state.positions:
            self._maybe_exit(bid, ask)

        # Update base price when no positions
        if not self.state.positions and abs(mid - self.state.base_price) >= config.grid_step_usd:
            self.state.base_price = align_to_grid(mid, config.grid_step_usd, config.strategy_side)
            save_state(self.args.state, vars(self.state))

    def run(self) -> None:
        """Run the trading loop."""
        logging.info(
            "Starting bot (dry_run=%s, testnet=%s) symbol=%s grid_size=%d spacing=%s",
            self.args.dry_run, self.args.testnet, self.args.symbol,
            self.args.grid_size, self.args.spacing
        )
        logging.info("Grid levels: %s", self.grid)

        self.price_manager.start()

        try:
            while not self.stop_evt.is_set():
                try:
                    bid, ask, mid = self.price_manager.get_price()
                except Exception:
                    time.sleep(1.0)
                    continue

                self.process_grid(bid, ask, mid)
                time.sleep(0.1)

        except KeyboardInterrupt:
            logging.info("Interrupted by user")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logging.info("Cleaning up...")
        try:
            save_state(self.args.state, vars(self.state))
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
        self.price_manager.stop()

    def _maybe_enter(self, bid: float, ask: float) -> None:
        """Handle potential entry positions."""
        # Implementation of entry logic 
        pass

    def _maybe_exit(self, bid: float, ask: float) -> None:
        """Handle potential exit positions."""
        # Implementation of exit logic
        pass


def main() -> None:
    """Main entry point."""
    init_logging()
    args = parse_args()

    if not args.dry_run and not args.confirm_live:
        logging.error(
            "Live trading requested but --confirm-live not provided. "
            "Exiting to avoid accidental live orders."
        )
        return

    if args.dry_run:
        os.environ.setdefault("DEMO_MID", str(args.mid))

    bot = GridBot(args)
    bot.initialize()
    
    def signal_handler(signum: int, frame) -> None:
        logging.info(f"Received signal {signum}, initiating shutdown...")
        bot.stop_evt.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bot.run()


if __name__ == "__main__":
    main()