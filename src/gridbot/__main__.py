import time
import threading
import queue
import signal
import datetime
from typing import Optional

from gridbot.config.settings import load_settings, Settings
from gridbot.state.manager import StateManager
from gridbot.broker.binance_connector import Broker
from gridbot.core.grid_logic import GridManager
from gridbot.core.utils import sync_server_time, set_debug_verbose, align_to_grid, spread_bps
from gridbot.price import refresh_prices, get_book, PriceMessage

# ===== Global Control and Threads =====
stop_evt = threading.Event()
price_thread: Optional[threading.Thread] = None
proc_thread: Optional[threading.Thread] = None
grid_manager: Optional[GridManager] = None
settings: Optional[Settings] = None
state_manager: Optional[StateManager] = None

def processor_loop(settings: Settings, state_manager: StateManager, grid_manager: GridManager, msg_queue: "queue.Queue[PriceMessage]", stop_evt: threading.Event):
    """The main processing loop that handles market data and executes logic."""
    state = state_manager.state
    last_status = 0.0

    # Initial setup
    try:
        _, _, mid = get_book(settings)
    except Exception:
        mid = 200.0 # Fallback
    
    state.base_price = grid_manager.broker.clamp_price(mid) # Use broker's precision
    state.base_price = grid_manager.broker.clamp_price(state.base_price) # Ensure precision
    state.base_price = grid_manager.broker.clamp_price(align_to_grid(mid, settings.GRID_STEP_USD))
    print(f"Base price aligned: {state.base_price:.0f}")

    grid_manager.sync_open_from_exchange_full()
    grid_manager.ensure_tps_for_positions()
    print("[ARMED] Grid placement enabled.")

    levels = grid_manager.build_grid_candidates(state.base_price)
    if not (stop_evt.is_set() or state.HALT_PLACEMENT):
        grid_manager.place_missing_buys(levels)
        state_manager.save_state()

    while not stop_evt.is_set():
        if state.HALT_PLACEMENT:
            print("[LOOP] HALT_PLACEMENT=True -> exiting processor loop")
            break
        
        # Daily reset check
        curr = datetime.datetime.now().strftime("%Y-%m-%d")
        if curr != state.spent_date:
            state.spent_today = 0.0
            state.spent_date = curr
            state_manager.save_state()
        
        try:
            bid, ask, mid = msg_queue.get(timeout=0.6)
        except queue.Empty:
            continue

        sp = spread_bps(bid, ask)
        if sp > settings.MAX_SPREAD_BPS:
            now = time.time()
            if now - last_status > settings.INTERVAL_STATUS_SEC:
                print(f"\nMid={mid:.4f} | Spread={sp:.2f}bps wide; waiting...", end="", flush=True)
                last_status = now
            continue

        grid_manager.reanchor_up_if_needed(mid)
        grid_manager.detect_filled_buys_and_restore()
        
        # Re-sync state after fill detection/reanchor to get latest TP blocks
        grid_manager.sync_open_from_exchange_full()
        
        levels = grid_manager.build_grid_candidates(state.base_price)
        if len(state.open_buy_price_to_id) < settings.MAX_LADDERS and not (stop_evt.is_set() or state.HALT_PLACEMENT):
            grid_manager.place_missing_buys(levels)
            state_manager.save_state()

        grid_manager.process_positions_vs_market(bid)

        now = time.time()
        if now - last_status > settings.INTERVAL_STATUS_SEC:
            print(
                f"\nMid={mid:.4f} | Spread={sp:.2f}bps | Base={state.base_price:.0f} | OpenBUYS={len(state.open_buy_price_to_id)}/{settings.MAX_LADDERS} | "
                f"TPBlocks={len(state.tp_blocked_entries)} | PosLots={len(state.positions)} | PnL=${state.realized_pnl:.2f}",
                end="",
                flush=True,
            )
            last_status = now


def graceful_exit(signum, frame):
    global grid_manager, state_manager, stop_evt
    print("\n[Signal] Graceful shutdown...")

    if state_manager:
        state_manager.state.HALT_PLACEMENT = True
        set_debug_verbose(state_manager.settings.DEBUG_VERBOSE) # Ensure dprint works
        print("[SHUTDOWN] HALT_PLACEMENT=True")

    stop_evt.set()

    if grid_manager and not grid_manager.settings.DRY_RUN:
        try:
            print("[INFO] Canceling active BUY orders...")
            for oid in list(grid_manager.state.open_buy_price_to_id.values()):
                grid_manager.broker.cancel_order(oid)
            grid_manager.state.open_buy_price_to_id.clear()
        except Exception as e:
            print(f"[WARN] selective cancel failed: {e}")

    if state_manager:
        try:
            state_manager.save_state()
        except Exception:
            pass

    try:
        if price_thread:
            price_thread.join(timeout=0.5)
        if proc_thread:
            proc_thread.join(timeout=0.5)
    except Exception:
        pass

    print("Bye!")


def main():
    global price_thread, proc_thread, grid_manager, settings, state_manager
    
    settings = load_settings()
    set_debug_verbose(settings.DEBUG_VERBOSE)
    
    mode = "DRY" if settings.DRY_RUN else ("TESTNET" if settings.USE_TESTNET else "LIVE")
    print(f"Starting {settings.SYMBOL} | Mode={mode}")

    broker = Broker(settings)
    
    # Update TAKER_FEE if auto-fetch succeeded
    if broker.taker_fee is not None:
        # Note: Settings is frozen, so we rely on the broker instance having the correct fee
        # The PnL calculation in GridManager uses broker.taker_fee if available.
        print(f"[FEES] TAKER_FEE used for PnL: {broker.taker_fee:.6f}")

    state_manager = StateManager(settings)
    state_manager.load_state()
    state_manager.init_csv()

    grid_manager = GridManager(settings, state_manager, broker)
    
    print(
        f"[CONFIG] SYMBOL={settings.SYMBOL} | GRID_STEP_USD={settings.GRID_STEP_USD} | TAKE_PROFIT_USD={settings.TAKE_PROFIT_USD} "
        f"| MAX_LADDERS={settings.MAX_LADDERS} | DRY_RUN={settings.DRY_RUN} | USE_TESTNET={settings.USE_TESTNET} | TRAIL_UP={settings.TRAIL_UP} | QTY_PER_LADDER={settings.QTY_PER_LADDER}"
    )

    print("[TIME] syncing...")
    sync_server_time(settings.FUTURES_BASE_URL)

    # Start threads
    msg_queue: "queue.Queue[PriceMessage]" = queue.Queue(maxsize=1000)
    price_thread = threading.Thread(target=refresh_prices, args=(settings, stop_evt, msg_queue), daemon=True)
    price_thread.start()
    proc_thread = threading.Thread(target=processor_loop, args=(settings, state_manager, grid_manager, msg_queue, stop_evt), daemon=True)
    proc_thread.start()

    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    try:
        while not stop_evt.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        graceful_exit(None, None)


if __name__ == "__main__":
    main()