import time
import threading
import queue
from typing import Tuple, Optional

from gridbot.config.settings import Settings
from gridbot.core.utils import request_with_retry

# Type alias for the message queue content: (bid, ask, mid)
PriceMessage = Tuple[float, float, float]

def get_book(settings: Settings) -> Tuple[float, float, float]:
    """Fetches the current best bid and ask prices."""
    d = request_with_retry(
        "GET",
        f"{settings.FUTURES_BASE_URL}/ticker/bookTicker",
        params={"symbol": settings.SYMBOL},
        timeout=4
    ).json()
    bid = float(d["bidPrice"])
    ask = float(d["askPrice"])
    mid = (bid + ask) / 2.0
    return bid, ask, mid

def refresh_prices(settings: Settings, stop_evt: threading.Event, msg_queue: "queue.Queue[PriceMessage]"):
    """Thread function to continuously fetch prices and put them into the queue."""
    while not stop_evt.is_set():
        try:
            bid, ask, mid = get_book(settings)
            try:
                msg_queue.put_nowait((bid, ask, mid))
            except queue.Full:
                # If the processor is too slow, skip this tick
                pass
        except Exception as e:
            print(f"[REFRESH] price fetch failed: {e}")
        
        time.sleep(max(0.1, settings.PRICE_REFRESH_SEC))