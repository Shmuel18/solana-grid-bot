import time
import requests
from typing import Tuple
from decimal import Decimal, ROUND_DOWN, ROUND_CEILING

# Global time offset for server time synchronization
_time_offset_ms = 0
_DEBUG_VERBOSE = True # Will be set by main

def set_debug_verbose(verbose: bool):
    global _DEBUG_VERBOSE
    _DEBUG_VERBOSE = verbose

def dprint(msg: str):
    if _DEBUG_VERBOSE:
        print(msg)

def ts_ms() -> int:
    """Returns current Unix timestamp in milliseconds, adjusted by server time offset."""
    return int(time.time() * 1000 + _time_offset_ms)

def sync_server_time(futures_base_url: str):
    """Synchronizes local time with Binance server time."""
    global _time_offset_ms
    try:
        r = requests.get(f"{futures_base_url}/time", timeout=5)
        r.raise_for_status()
        server_time = int(r.json().get("serverTime", 0))
        _time_offset_ms = server_time - int(time.time() * 1000)
        print(f"[TIME] server-local offset: {_time_offset_ms} ms")
    except Exception as e:
        print(f"[WARN] time sync failed: {e}")

def _decimal_places(step: float) -> int:
    """Calculates the number of decimal places in a float step."""
    ds = Decimal(str(step)).normalize()
    return -ds.as_tuple().exponent if ds.as_tuple().exponent < 0 else 0

def format_step(x: float, step: float) -> str:
    """Formats a float to align with a given step size (e.g., price or quantity precision)."""
    dx = Decimal(str(x))
    ds = Decimal(str(step))
    # Use ROUND_DOWN for quantity/price clamping to ensure we don't exceed limits
    q = (dx / ds).to_integral_value(rounding=ROUND_DOWN) * ds
    exp = _decimal_places(step)
    return format(q, f".{exp}f")

def spread_bps(bid: float, ask: float) -> float:
    """Calculates the spread in basis points (BPS)."""
    if ask <= 0:
        return 9999
    return (ask - bid) / ask * 10000

def align_to_grid(mid: float, step: float) -> float:
    """Aligns a mid-price to the nearest grid step (rounded up)."""
    dm = Decimal(str(mid))
    ds = Decimal(str(step))
    # Use ROUND_CEILING to ensure the base price is always above the mid-price
    return float(((dm / ds).to_integral_value(rounding=ROUND_CEILING)) * ds)

def request_with_retry(method: str, url: str, *, headers=None, data=None, params=None, timeout=5.0, retries=3):
    """Performs an HTTP request with exponential backoff retry logic."""
    delay = 0.5
    for i in range(retries):
        try:
            r = requests.request(method, url, headers=headers, data=data, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            dprint(f"[WARN] HTTP Error {e.response.status_code} on {url} (Attempt {i+1}/{retries})")
            if i == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
        except requests.exceptions.RequestException as e:
            dprint(f"[WARN] Request Error on {url}: {e} (Attempt {i+1}/{retries})")
            if i == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)

def sanitize_tag(tag: str, max_len: int = 6) -> str:
    """Sanitizes a session tag for use in client order IDs."""
    s = ''.join(ch for ch in tag if ch.isalnum() or ch in ('-', '_'))
    if len(s) > max_len:
        s = s[:max_len]
    return s or "r"