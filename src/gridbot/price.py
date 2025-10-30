"""Price streaming and management."""

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import websocket

from .broker.binance_connector import BinanceConnector
from .config.settings import config
from .core.utils import request_with_retry


@dataclass
class PriceTick:
    """Price tick data."""
    bid: float
    ask: float
    mid: float
    timestamp: float


class PriceQueue:
    """Thread-safe price queue."""
    def __init__(self, maxsize: int = 1000):
        self.queue: "queue.Queue[PriceTick]" = queue.Queue(maxsize=maxsize)
        self.last_tick_time = 0.0

    def put(self, tick: PriceTick) -> None:
        """Add price tick to queue."""
        try:
            self.queue.put_nowait(tick)
            self.last_tick_time = time.time()
        except queue.Full:
            # Silently drop ticks if queue is full
            pass

    def get(self, timeout: float = 1.0) -> Optional[PriceTick]:
        """Get price tick from queue."""
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None


class WebSocketManager:
    """WebSocket price stream manager."""

    def __init__(self, url: str, price_queue: PriceQueue):
        """Initialize WebSocket manager."""
        self.url = url
        self.price_queue = price_queue
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.stop_evt = threading.Event()
        self.reconnect_delay = config.reconnect_min

    def on_message(self, ws, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            bid, ask = float(data["b"]), float(data["a"])
            mid = (bid + ask) / 2.0
            tick = PriceTick(bid=bid, ask=ask, mid=mid, timestamp=time.time())
            self.price_queue.put(tick)
        except Exception as e:
            logging.warning(f"Failed to process WS message: {e}")

    def on_error(self, ws, error: Exception) -> None:
        """Handle WebSocket error."""
        logging.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code: int, close_msg: str) -> None:
        """Handle WebSocket close."""
        logging.info(f"WebSocket closed: {close_status_code} {close_msg}")

    def on_open(self, ws) -> None:
        """Handle WebSocket open."""
        logging.info("WebSocket connected")
        self.reconnect_delay = config.reconnect_min

    def _run_websocket(self) -> None:
        """Run WebSocket connection with auto-reconnect."""
        while not self.stop_evt.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                self.ws.run_forever(
                    ping_interval=config.ping_interval,
                    ping_timeout=config.ping_timeout
                )
            except Exception as e:
                logging.error(f"WebSocket error: {e}")

            if self.stop_evt.is_set():
                break

            delay = min(self.reconnect_delay, config.reconnect_max)
            logging.info(f"Reconnecting in {delay:.1f}s...")
            time.sleep(delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, config.reconnect_max)

    def start(self) -> None:
        """Start WebSocket manager."""
        self.thread = threading.Thread(target=self._run_websocket)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop WebSocket manager."""
        self.stop_evt.set()
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=3.0)


class RestPriceManager:
    """REST API price manager for backup/validation."""

    def __init__(self, symbol: str, connector: BinanceConnector, price_queue: PriceQueue):
        """Initialize REST price manager."""
        self.symbol = symbol
        self.connector = connector
        self.price_queue = price_queue
        self.thread: Optional[threading.Thread] = None
        self.stop_evt = threading.Event()
        self.last_rest_call = 0.0

    def _fetch_price(self) -> Optional[PriceTick]:
        """Fetch current price via REST API."""
        try:
            ticker = self.connector.get_ticker(self.symbol)
            bid = float(ticker["bid"])
            ask = float(ticker["ask"])
            mid = float(ticker.get("mid", (bid + ask) / 2.0))
            return PriceTick(bid=bid, ask=ask, mid=mid, timestamp=time.time())
        except Exception as e:
            logging.warning(f"REST price fetch failed: {e}")
            return None

    def _run_price_refresh(self) -> None:
        """Run price refresh loop."""
        while not self.stop_evt.is_set():
            now = time.time()
            time_since_last_ws = now - self.price_queue.last_tick_time

            # Always refresh if WS is stale
            if time_since_last_ws >= config.stale_ws_sec:
                tick = self._fetch_price()
                if tick:
                    self.price_queue.put(tick)
                    logging.debug(
                        f"WS silent for {time_since_last_ws:.1f}s; "
                        "using REST prices"
                    )
            
            # Throttled refresh for validation
            elif now - self.last_rest_call >= config.price_refresh_sec:
                tick = self._fetch_price()
                if tick:
                    self.price_queue.put(tick)
                self.last_rest_call = now

            time.sleep(0.1)

    def start(self) -> None:
        """Start REST price manager."""
        self.thread = threading.Thread(target=self._run_price_refresh)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop REST price manager."""
        self.stop_evt.set()
        if self.thread:
            self.thread.join(timeout=3.0)


class PriceManager:
    """Combined price management system."""

    def __init__(self, symbol: str):
        """Initialize price management system."""
        self.symbol = symbol
        self.connector = BinanceConnector()
        self.price_queue = PriceQueue()
        self.ws_manager = WebSocketManager(config.ws_url, self.price_queue)
        self.rest_manager = RestPriceManager(symbol, self.connector, self.price_queue)

    def start(self) -> None:
        """Start price management system."""
        self.ws_manager.start()
        self.rest_manager.start()

    def stop(self) -> None:
        """Stop price management system."""
        self.ws_manager.stop()
        self.rest_manager.stop()

    def get_price(self, timeout: float = 1.0) -> Tuple[float, float, float]:
        """Get current price data."""
        tick = self.price_queue.get(timeout=timeout)
        if not tick:
            raise RuntimeError("No price data available")
        return tick.bid, tick.ask, tick.mid

    def get_ticker(self) -> Dict[str, float]:
        """Get current ticker data."""
        tick = self.price_queue.get()
        if not tick:
            raise RuntimeError("No price data available")
        return {
            "symbol": self.symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "mid": tick.mid
        }