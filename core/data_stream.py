"""Data stream helpers (WS / polling) - skeleton.

This module contains a minimal class to represent a data stream source. In a
real implementation replace the placeholders with aiohttp/websockets and
reconnection logic.
"""
from typing import Callable, Optional


class DataStream:
    def __init__(self) -> None:
        self._running = False
        self._on_message: Optional[Callable[[dict], None]] = None

    def on_message(self, cb: Callable[[dict], None]) -> None:
        """Register a callback that will be called with incoming messages."""
        self._on_message = cb

    def start(self) -> None:
        """Start polling/WS loop. Placeholder (blocking)."""
        self._running = True

    def stop(self) -> None:
        """Stop the stream."""
        self._running = False
