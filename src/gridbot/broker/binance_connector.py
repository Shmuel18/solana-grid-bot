import time
import uuid
import hmac
import hashlib
from typing import Dict, Tuple, List, Optional
from urllib.parse import urlencode

from gridbot.config.settings import Settings
from gridbot.core.utils import ts_ms, format_step, request_with_retry, dprint, sanitize_tag

class Broker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.order_nonce = 0
        self.tick_size = 0.01
        self.step_size = 0.1
        self.min_qty = 0.1
        self.min_notional = 5.0
        self.price_precision = 2
        self.qty_precision = 3
        self.session_tag = self._get_session_tag()
        self.maker_fee: Optional[float] = None
        self.taker_fee: Optional[float] = None

        if not self.settings.DRY_RUN:
            self._fetch_exchange_info()
            self._set_margin_mode()
            if self.settings.AUTO_FEE:
                self._fetch_commission_rates()

        print("Broker ready.")

    def _get_session_tag(self) -> str:
        tag_env = self.settings.SESSION_TAG_ENV
        if tag_env:
            return sanitize_tag(tag_env)
        return f"r{int(time.time()) % 100000}"

    def _sign_request(self, params: dict) -> str:
        q = urlencode(params, True)
        sig = hmac.new(self.settings.API_SECRET.encode("utf-8"), q.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{q}&signature={sig}"

    def _fetch_exchange_info(self):
        try:
            sym = request_with_retry(
                "GET",
                f"{self.settings.FUTURES_BASE_URL}/exchangeInfo",
                params={"symbol": self.settings.SYMBOL}
            ).json()["symbols"][0]
            for f in sym.get("filters", []):
                if f.get("filterType") == "PRICE_FILTER":
                    self.tick_size = float(f.get("tickSize", self.tick_size))
                if f.get("filterType") == "LOT_SIZE":
                    self.step_size = float(f.get("stepSize", self.step_size))
                    self.min_qty = float(f.get("minQty", self.min_qty))
                if f.get("filterType") == "MIN_NOTIONAL":
                    self.min_notional = float(f.get("notional", self.min_notional))
            self.price_precision = int(sym.get("pricePrecision", self.price_precision))
            self.qty_precision = int(sym.get("quantityPrecision", self.qty_precision))
            print(
                f"[SYMBOL INFO] tick={self.tick_size} step={self.step_size} "
                f"min_qty={self.min_qty} notional>={self.min_notional} "
                f"pricePrecision={self.price_precision} qtyPrecision={self.qty_precision}"
            )
        except Exception as e:
            print(f"[WARN] exchangeInfo failed: {e}")

    def _set_margin_mode(self):
        try:
            p = {'timestamp': ts_ms(), 'recvWindow': 50000, 'symbol': self.settings.SYMBOL, 'marginType': self.settings.MARGIN_MODE}
            signed = self._sign_request(p)
            request_with_retry(
                "POST",
                f"{self.settings.FUTURES_BASE_URL}/marginType",
                headers={'X-MBX-APIKEY': self.settings.API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'},
                data=signed.encode("utf-8"),
            )
        except Exception as e:
            print(f"[WARN] set_margin_mode failed: {e}")

    def _fetch_commission_rates(self):
        try:
            params = {'symbol': self.settings.SYMBOL, 'timestamp': ts_ms(), 'recvWindow': 50000}
            signed = self._sign_request(params)
            url = f"{self.settings.FUTURES_BASE_URL}/commissionRate?{signed}"
            r = request_with_retry("GET", url, headers={'X-MBX-APIKEY': self.settings.API_KEY}, timeout=5.0)
            d = r.json()
            self.maker_fee = float(d.get("makerCommissionRate", 0.0))
            self.taker_fee = float(d.get("takerCommissionRate", 0.0))
            print(f"[FEES] maker={self.maker_fee:.6f} taker={self.taker_fee:.6f}")
        except Exception as e:
            print(f"[WARN] fetch_commission_rates failed: {e}")

    def clamp_price(self, p: float) -> float:
        return float(format_step(p, self.tick_size))

    def clamp_qty(self, q: float) -> float:
        return float(format_step(max(q, self.min_qty), self.step_size))

    def _cid(self, prefix: str, price: float) -> str:
        self.order_nonce = (self.order_nonce + 1) % 1000000
        cents = int(round(price * 100))
        cid = f"{prefix}-{self.session_tag}-{cents}-{self.order_nonce}"
        return cid[:32]

    def _futures_order(self, params: dict) -> dict:
        if self.settings.DRY_RUN:
            return {
                "orderId": f"dry-{uuid.uuid4().hex[:8]}",
                "status": "NEW",
                "price": params.get("price", "0"),
                "side": params.get("side", ""),
            }

        def _do(p):
            p = dict(p)
            p.setdefault("timestamp", ts_ms())
            p.setdefault("recvWindow", 50000)
            signed = self._sign_request(p)
            return request_with_retry(
                "POST",
                f"{self.settings.FUTURES_BASE_URL}/order",
                headers={'X-MBX-APIKEY': self.settings.API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'},
                data=signed.encode("utf-8"),
            )

        r = _do(params)
        try:
            return r.json()
        except Exception:
            return {"orderId": "n/a", "status": "UNKNOWN"}

    def limit_buy(self, price: float, qty: float) -> dict:
        qty = self.clamp_qty(qty)
        price = self.clamp_price(price)
        if not self.settings.DRY_RUN and price * qty < self.min_notional:
            # Adjust quantity up to meet min notional
            qty = self.clamp_qty(self.min_notional / price + self.step_size)

        cid = self._cid("B", price)
        params = {
            'symbol': self.settings.SYMBOL,
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': format_step(qty, self.step_size),
            'price': format_step(price, self.tick_size),
            'newClientOrderId': cid,
        }
        od = self._futures_order(params)
        dprint(f"[DEBUG] BUY attempt @ {price}: {od}")
        return od

    def limit_tp_reduce(self, entry: float, qty: float, client_order_id: Optional[str] = None) -> dict:
        exit_price = self.clamp_price(entry + self.settings.TAKE_PROFIT_USD)
        qty = self.clamp_qty(qty)
        cid = client_order_id or self._cid("T", exit_price)
        params = {
            'symbol': self.settings.SYMBOL,
            'side': 'SELL',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': format_step(qty, self.step_size),
            'price': format_step(exit_price, self.tick_size),
            'reduceOnly': 'true',
            'newClientOrderId': cid,
        }
        od = self._futures_order(params)
        dprint(f"[DEBUG] TP attempt @ {exit_price} for entry {entry} qty {qty}: {od}")
        return od

    def cancel_order(self, order_id: str) -> None:
        if self.settings.DRY_RUN:
            return
        try:
            p = {'timestamp': ts_ms(), 'recvWindow': 50000, 'symbol': self.settings.SYMBOL, 'orderId': order_id}
            signed = self._sign_request(p)
            request_with_retry(
                "DELETE",
                f"{self.settings.FUTURES_BASE_URL}/order?{signed}",
                headers={'X-MBX-APIKEY': self.settings.API_KEY},
            )
        except Exception as e:
            print(f"[WARN] cancel_order({order_id}) failed: {e}")

    def get_open_orders(self) -> List[Dict]:
        if self.settings.DRY_RUN:
            return []
        try:
            p = {'timestamp': ts_ms(), 'recvWindow': 50000, 'symbol': self.settings.SYMBOL}
            signed = self._sign_request(p)
            return request_with_retry(
                "GET",
                f"{self.settings.FUTURES_BASE_URL}/openOrders?{signed}",
                headers={'X-MBX-APIKEY': self.settings.API_KEY},
            ).json()
        except Exception as e:
            print(f"[WARN] get_open_orders failed: {e}")
            return []

    def get_order(self, order_id: str) -> Optional[Dict]:
        if self.settings.DRY_RUN:
            return {"status": "NEW", "executedQty": "0", "origQty": str(self.settings.QTY_PER_LADDER)}
        try:
            p = {'timestamp': ts_ms(), 'recvWindow': 50000, 'symbol': self.settings.SYMBOL, 'orderId': order_id}
            signed = self._sign_request(p)
            return request_with_retry(
                "GET",
                f"{self.settings.FUTURES_BASE_URL}/order?{signed}",
                headers={'X-MBX-APIKEY': self.settings.API_KEY},
            ).json()
        except Exception as e:
            if "-2011" in str(e):
                return {"status": "NOT_FOUND", "executedQty": "0", "origQty": str(self.settings.QTY_PER_LADDER)}
            dprint(f"[WARN] get_order failed for {order_id}: {e}")
            return None