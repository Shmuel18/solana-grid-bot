"""Run a safe demo of the bot skeleton.

This demo computes grid levels from the strategy module and optionally
queries the connector in dry-run mode. It is safe by default and will not
place real orders unless you explicitly construct the connector with
`dry_run=False` and provide API credentials.
"""
import os
import argparse
from strategy.grid_logic import compute_grid_levels
from broker.binance_connector import BinanceConnector


def main():
    p = argparse.ArgumentParser(description="Run demo for solana-grid-bot (safe default)")
    p.add_argument("--mid", type=float, default=float(os.getenv("DEMO_MID", "100.0")), help="Mid price to base the grid on")
    p.add_argument("--size", type=int, default=int(os.getenv("DEMO_GRID_SIZE", "5")), help="Grid size")
    p.add_argument("--spacing", type=float, default=float(os.getenv("DEMO_GRID_SPACING", "1.0")), help="Grid spacing")
    p.add_argument("--symbol", default=os.getenv("DEMO_SYMBOL", "SOLUSDT"), help="Symbol to query (used only for ticker in dry-run)")
    p.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run (no real orders)")
    args = p.parse_args()

    print(f"Demo grid | mid={args.mid} size={args.size} spacing={args.spacing}")
    levels = compute_grid_levels(args.mid, args.size, args.spacing)
    print("Computed grid levels (ascending):")
    for lv in levels:
        print(f" - {lv}")

    # Show connector usage in dry-run
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    use_testnet = os.getenv("BINANCE_USE_TESTNET", "yes").lower() in ("yes", "true", "1")

    conn = BinanceConnector(api_key=api_key, api_secret=api_secret, use_testnet=use_testnet, dry_run=True)
    ticker = conn.get_ticker(args.symbol)
    print(f"Ticker (dry-run): {ticker}")

    print("Demo finished — no orders placed.")


if __name__ == "__main__":
    main()
