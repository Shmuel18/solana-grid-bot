"""Binance connector with optional real-API support (synchronous).

This connector supports three modes determined at construction:
- dry_run (default True): no network calls, returns simulated responses.
- real API (dry_run=False) with API key/secret: will call Binance Futures
  endpoints (optionally Testnet) for ticker and order placement.

This implementation is intentionally small and synchronous. For
production/low-latency use prefer an async aiohttp-based connector and
robust retry/backoff and rate-limiting logic.
"""
from typing import Dict, Any, Optional
import time
import hmac
import hashlib
from urllib.parse import urlencode
import requests
import threading
import math


class BinanceConnector:
    """Simplified synchronous connector.

    Args:
        api_key: API key for private endpoints (optional).
        api_secret: API secret for signing (optional).
        use_testnet: if True use Binance Futures testnet base URLs.
        dry_run: if True do not perform real trades (default True).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        use_testnet: bool = False,
        dry_run: bool = True,
        timeout: float = 5.0,
        rate_limit_per_sec: float = 10.0,
        demo_mid: Optional[float] = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.use_testnet = use_testnet
        self.dry_run = dry_run
        self.timeout = timeout
        self.demo_mid = demo_mid

        self._http = requests.Session()
        if self.api_key:
            self._http.headers.update({"X-MBX-APIKEY": self.api_key})

        if self.use_testnet:
            self.FUTURES_HTTP_BASE = "https://testnet.binancefuture.com"
        else:
            self.FUTURES_HTTP_BASE = "https://fapi.binance.com"

        self.FUTURES_BASE_URL = f"{self.FUTURES_HTTP_BASE}/fapi/v1"
        self.FUTURES_ORDER_URL = f"{self.FUTURES_HTTP_BASE}/fapi/v1/order"

    # Simple token-bucket rate limiter
    self._rate_lock = threading.Lock()
    self._rate_capacity = max(1.0, float(rate_limit_per_sec))
    self._rate_tokens = self._rate_capacity
    self._rate_last = time.time()

    def _sign(self, params: Dict[str, Any]) -> str:
        qs = urlencode(params, True)
        if not self.api_secret:
            raise RuntimeError("API secret required for signing requests")
        signature = hmac.new(self.api_secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{qs}&signature={signature}"

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Return ticker info for `symbol`.

        In dry-run mode returns a simulated ticker. Otherwise queries the
        `bookTicker` endpoint and constructs a simple dict.
        """
        if self.dry_run:
            # In dry-run, return demo mid if provided, otherwise zeros
            if self.demo_mid is not None:
                bid = ask = float(self.demo_mid)
                mid = float(self.demo_mid)
            else:
                bid = ask = mid = 0.0
            return {"symbol": symbol, "bid": bid, "ask": ask, "mid": mid}

        url = f"{self.FUTURES_BASE_URL}/ticker/bookTicker"
        # real request with retries
        resp = self._request_with_retry("GET", url, params={"symbol": symbol})
        d = resp.json()
        bid = float(d.get("bidPrice", 0.0))
        ask = float(d.get("askPrice", 0.0))
        mid = (bid + ask) / 2.0 if ask > 0 else 0.0
        return {"symbol": symbol, "bid": bid, "ask": ask, "mid": mid}

    def place_order(self, symbol: str, side: str, quantity: float, price: Optional[float] = None, order_type: str = "LIMIT") -> Dict[str, Any]:
        """Place an order.

        In dry-run mode returns a simulated filled order. In real mode calls
        the Futures `order` endpoint. Only a limited set of params are
        supported here; expand as needed.
        """
        if self.dry_run or not self.api_key or not self.api_secret:
            return {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "status": "simulated",
            }

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type,
            "quantity": quantity,
            "timestamp": int(time.time() * 1000),
        }
        if price is not None:
            params["price"] = price

        qs = self._sign(params)
        resp = self._request_with_retry("POST", self.FUTURES_ORDER_URL, data=qs)
        return resp.json()


    def _acquire_rate_token(self) -> None:
        """Simple token bucket: block until token available."""
        while True:
            with self._rate_lock:
                now = time.time()
                elapsed = now - self._rate_last
                # refill
                self._rate_tokens = min(self._rate_capacity, self._rate_tokens + elapsed * self._rate_capacity)
                self._rate_last = now
                if self._rate_tokens >= 1.0:
                    self._rate_tokens -= 1.0
                    return
                # compute sleep time until next token
                need = 1.0 - self._rate_tokens
                sleep_for = need / max(1e-6, self._rate_capacity)
            time.sleep(sleep_for)


    def _request_with_retry(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, data: Optional[Any] = None, timeout: Optional[float] = None, retries: int = 3):
        timeout = timeout or self.timeout
        delay = 0.5
        for attempt in range(retries):
            try:
                # rate limit
                self._acquire_rate_token()
                if method.upper() == "GET":
                    r = self._http.get(url, params=params, timeout=timeout)
                else:
                    # POST with data
                    r = self._http.post(url, data=data, timeout=timeout)
                if r.status_code == 429:
                    # respect Retry-After if provided
                    ra = r.headers.get("Retry-After")
                    wait = float(ra) if ra else delay
                    if attempt == retries - 1:
                        r.raise_for_status()
                    time.sleep(wait)
                    delay = min(delay * 2, 8.0)
                    continue
                r.raise_for_status()
                return r
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 8.0)


__all__ = ["BinanceConnector"]
