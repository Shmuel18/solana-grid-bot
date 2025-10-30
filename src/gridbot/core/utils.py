"""Utility functions and helpers."""

import csv
import datetime
import os
import threading
from typing import List

from ..utils.logger import get_logger

logger = get_logger(__name__)

import requests
from requests import Response

from ..config.settings import config


def spread_bps(bid: float, ask: float) -> float:
    """Calculate spread in basis points."""
    if ask <= 0:
        return 9999.0
    return (ask - bid) / ask * 10_000


def init_csv() -> None:
    """Initialize CSV file with headers if needed."""
    new = not os.path.exists(config.csv_file)
    with open(config.csv_file, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow([
                "time", "side", "price", "qty", "pnl", "total_pnl",
                "bid", "ask", "spread_bps", "note"
            ])


def log_trade(side: str, price: float, qty: float, pnl: float, total: float,
              bid: float, ask: float, spread_bps_val: float, note: str = "") -> None:
    """Log trade details to CSV file."""
    with open(config.csv_file, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            side, f"{price:.4f}", f"{qty:.6f}", f"{pnl:.4f}", f"{total:.4f}",
            f"{bid:.4f}", f"{ask:.4f}", f"{spread_bps_val:.3f}", note
        ])


def append_csv_row(filepath: str, row: List[str]) -> None:
    """Append a row to CSV file."""
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def request_with_retry(method: str, url: str, *, headers=None, data=None, params=None,
                      timeout: float = 5.0, retries: int = 3) -> Response:
    """Make HTTP request with retries and backoff."""
    delay = 0.5
    for i in range(retries):
        try:
            r = requests.request(method, url, headers=headers, data=data, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            ra = e.response.headers.get("Retry-After")
            if ra:
                try:
                    wait = max(float(ra), delay)
                except:
                    wait = delay
            else:
                wait = delay
            if i == retries - 1:
                raise
            if i == 0:
                logger.warning(f"[HTTP RETRY] {method} {url} failed ({e.response.status_code}). Retrying...")
            threading.Event().wait(wait)
            delay = min(delay * 2, 8.0)
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                raise
            if i == 0:
                logger.warning(f"[HTTP RETRY] {method} {url} failed ({e.__class__.__name__}). Retrying...")
            threading.Event().wait(delay)
            delay = min(delay * 2, 8.0)