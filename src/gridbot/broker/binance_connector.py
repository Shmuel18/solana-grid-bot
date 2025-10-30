"""Binance Futures connector implementation."""

from decimal import ROUND_DOWN, Decimal
import hmac
import hashlib
import logging
import time
import uuid
from typing import Dict, Optional
from urllib.parse import urlencode

import requests

from ..config.settings import config
from ..core.utils import request_with_retry
from .notifications import send_telegram_message


_server_time_offset_ms = 0


def ts_ms() -> int:
    """Return synchronized timestamp (serverTime + offset)."""
    return int(time.time() * 1000 + _server_time_offset_ms)


def sync_server_time() -> None:
    """Synchronize local time with Binance server time."""
    global _server_time_offset_ms
    try:
        url = f"{config.futures_base_url}/time"
        r = request_with_retry('GET', url, timeout=5)
        server_time = int(r.json().get("serverTime", 0))
        local_time = int(time.time() * 1000)
        _server_time_offset_ms = server_time - local_time
        logging.info(f"Server-local offset: {_server_time_offset_ms} ms")
    except Exception as e:
        logging.warning(f"Time sync failed: {e}")


def _decimal_places(step: float) -> int:
    """Get number of decimal places in step size."""
    ds = Decimal(str(step)).normalize()
    return -ds.as_tuple().exponent if ds.as_tuple().exponent < 0 else 0


def _format_to_step(x: float, step: float, mode=ROUND_DOWN) -> str:
    """Format value to valid step increment."""
    dx = Decimal(str(x))
    ds = Decimal(str(step))
    q = (dx / ds).to_integral_value(rounding=mode) * ds
    exp = _decimal_places(step)
    return format(q, f".{exp}f")


def _round_to_step_float(x: float, step: float, mode=ROUND_DOWN) -> float:
    """Round value to step increment as float."""
    return float(_format_to_step(x, step, mode=mode))


def sign_request(params: dict) -> str:
    """Sign request parameters with API secret."""
    query_string = urlencode(params, True)
    signature = hmac.new(
        config.api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"{query_string}&signature={signature}"


class BinanceConnector:
    """Binance Futures API connector."""
    
    def __init__(self):
        if config.dry_run:
            self.is_hedge_mode = False
            # Default settings similar to SOLUSDT Futures
            self.step_size = 0.1
            self.tick_size = 0.01
            self.min_qty = 0.1 
            self.min_notional = 5.0
            self.qty_prec = _decimal_places(self.step_size)
            self.price_prec = _decimal_places(self.tick_size)
            return

        # Load exchange info and filters
        try:
            sym = self._futures_exchange_info(config.symbol)
        except Exception as e:
            logging.warning(f"Exchange info failed, using defaults: {e}")
            sym = {
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.1", "minQty": "0.1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5.0"}
                ]
            }

        # Extract trading filters
        price_f = self._get_filter(sym, "PRICE_FILTER")
        lot_f = self._get_filter(sym, "LOT_SIZE") 
        notional_f = self._get_filter(sym, "MIN_NOTIONAL")

        self.tick_size = float(price_f.get("tickSize", "0.01"))
        self.step_size = float(lot_f.get("stepSize", "0.1"))
        self.min_qty = float(lot_f.get("minQty", "0.1"))
        self.min_notional = float(notional_f.get("notional", "5.0"))

        self.price_prec = _decimal_places(self.tick_size)
        self.qty_prec = _decimal_places(self.step_size)

        # Detect and configure position mode
        self.is_hedge_mode = self.detect_position_mode()

        # Enforce desired position mode if specified
        if config.desired_position_mode in ("HEDGE", "ONEWAY"):
            want_hedge = (config.desired_position_mode == "HEDGE")
            if want_hedge != self.is_hedge_mode:
                ok = self.set_position_mode(want_hedge)
                if ok:
                    self.is_hedge_mode = want_hedge 
                else:
                    send_telegram_message(
                        f"⚠️ Failed to set position mode to {config.desired_position_mode}. "
                        f"Remain: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}*."
                    )

        # Configure margin type (best-effort)
        if config.margin_mode != "ISOLATED":
            self.set_margin_mode(config.margin_mode)

        send_telegram_message(
            f"ℹ️ Position mode: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}* | "
            f"Margin: *{config.margin_mode}*"
        )

    @staticmethod
    def _get_filter(sym: dict, filter_type: str) -> dict:
        """Get specific filter from symbol info."""
        for f in sym.get("filters", []):
            if f.get("filterType") == filter_type:
                return f
        return {}

    def _futures_exchange_info(self, symbol: str) -> dict:
        """Get exchange info for symbol."""
        url = f"{config.futures_base_url}/exchangeInfo"
        r = request_with_retry('GET', url, params={"symbol": symbol})
        return r.json()["symbols"][0]

    def refresh_symbol_filters(self) -> None:
        """Refresh trading filters from exchange."""
        try:
            sym = self._futures_exchange_info(config.symbol)
            price_f = self._get_filter(sym, "PRICE_FILTER")
            lot_f = self._get_filter(sym, "LOT_SIZE")
            notional_f = self._get_filter(sym, "MIN_NOTIONAL")

            self.tick_size = float(price_f.get("tickSize", self.tick_size))
            self.step_size = float(lot_f.get("stepSize", self.step_size))
            self.min_qty = float(lot_f.get("minQty", self.min_qty))
            self.min_notional = float(notional_f.get("notional", self.min_notional))

            self.price_prec = _decimal_places(self.tick_size)
            self.qty_prec = _decimal_places(self.step_size)
        except Exception as e:
            logging.warning(f"Failed to refresh filters: {e}")

    def detect_position_mode(self) -> bool:
        """Detect if account is in hedge mode."""
        if config.dry_run:
            return False
            
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': config.api_key}
            url = f"{config.futures_base_url}/positionSide/dual?{signed}"
            r = request_with_retry('GET', url, headers=headers)
            return bool(r.json().get("dualSidePosition", False))
        except Exception as e:
            logging.warning(f"Position mode detection failed: {e}")
            return False

    def set_position_mode(self, want_hedge: bool) -> bool:
        """Configure hedge mode setting."""
        if config.dry_run:
            return True
            
        try:
            params = {
                'timestamp': ts_ms(),
                'recvWindow': 15000,
                'dualSidePosition': 'true' if want_hedge else 'false'
            }
            signed = sign_request(params)
            headers = {
                'X-MBX-APIKEY': config.api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            url = f"{config.futures_base_url}/positionSide/dual"
            request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            return True
        except Exception as e:
            logging.warning(f"Failed to set position mode: {e}")
            return False

    def set_margin_mode(self, margin_type: str) -> bool:
        """Configure margin type."""
        if config.dry_run:
            return True
            
        try:
            params = {
                'timestamp': ts_ms(),
                'recvWindow': 15000,
                'symbol': config.symbol,
                'marginType': margin_type
            }
            signed = sign_request(params)
            headers = {
                'X-MBX-APIKEY': config.api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            url = f"{config.futures_base_url}/marginType"
            request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            send_telegram_message(f"✅ *Margin mode set to {margin_type}*")
            return True
        except Exception as e:
            err_text = getattr(e, 'response', None) and getattr(e.response, 'text', str(e))
            logging.warning(f"Failed to set margin mode: {err_text}")
            send_telegram_message(
                f"⚠️ Failed to set margin mode to {margin_type}.\n"
                f"Common causes: open positions/orders or already in requested mode.\n{err_text}"
            )
            return False

    def get_position_qty(self, symbol: str, side: str, live_positions: Dict[str, float]) -> float:
        """Get position quantity for specified side."""
        if not live_positions:
            return 0.0
        if self.is_hedge_mode:
            return live_positions.get(side, 0.0)
        return live_positions.get('BOTH', 0.0)

    def _fetch_live_positions(self, symbol: str) -> Dict[str, float]:
        """Fetch current position data."""
        if config.dry_run:
            return {}
            
        try:
            params = {
                'timestamp': ts_ms(),
                'recvWindow': 15000,
                'symbol': symbol
            }
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': config.api_key}
            url = f"{config.futures_account_url}/positionRisk?{signed}"
            r = request_with_retry('GET', url, headers=headers)
            arr = r.json()
            live_q = {"LONG": 0.0, "SHORT": 0.0, "BOTH": 0.0}
            
            if not isinstance(arr, list):
                arr = [arr]
                
            for p in arr:
                if p.get('symbol') != symbol:
                    continue
                ps = p.get('positionSide', 'BOTH')
                size = float(p.get('positionAmt', 0.0) or 0.0)
                live_q[ps] = max(live_q.get(ps, 0.0), abs(size))
                
            return live_q
        except Exception as e:
            logging.warning(f"Failed to fetch positions: {e}")
            return {}

    def balance_usdt(self) -> float:
        """Get available USDT balance."""
        if config.dry_run:
            return 999999.0

        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': config.api_key}
            url = f"{config.futures_account_url}/balance?{signed}"
            r = request_with_retry('GET', url, headers=headers)
            bal = r.json()
            
            for b in bal:
                if b.get("asset") == "USDT":
                    return float(b.get("availableBalance", 0.0))
            return 0.0
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return config.copy_trade_balance
            return 0.0
        except Exception:
            return 0.0

    def futures_order(self, params: dict, is_open: bool) -> dict:
        """Place futures order with automatic error handling."""
        def _do(p):
            p = dict(p)
            p.setdefault('timestamp', ts_ms())
            p.setdefault('recvWindow', 15000)
            signed = sign_request(p)
            headers = {
                'X-MBX-APIKEY': config.api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            url = f"{config.futures_base_url}/order"
            r = request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            return r

        try:
            return _do(params).json()
        except requests.exceptions.HTTPError as e:
            txt = (e.response.text or "")

            # Handle -1021: timestamp error
            if '"code":-1021' in txt or "-1021" in txt:
                logging.info("-1021: syncing server time and retrying once...")
                sync_server_time()
                try:
                    p2 = dict(params)
                    p2['timestamp'] = ts_ms()
                    p2['recvWindow'] = 15000
                    return _do(p2).json()
                except Exception as ee:
                    logging.error(f"Retry -1021 failed: {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            # Handle -1111: precision/quantity error 
            if '"code":-1111' in txt or "-1111" in txt:
                logging.info("-1111: refreshing filters + reclamp qty/price and retrying once...")
                try:
                    self.refresh_symbol_filters()
                    p2 = dict(params)
                    if 'quantity' in p2:
                        qf = float(p2['quantity'])
                        p2['quantity'] = _format_to_step(qf, self.step_size, mode=ROUND_DOWN)
                    if 'price' in p2:
                        pf = float(p2['price'])
                        p2['price'] = _format_to_step(pf, self.tick_size, mode=ROUND_DOWN)
                    p2['timestamp'] = ts_ms()
                    p2['recvWindow'] = 15000
                    return _do(p2).json()
                except Exception as ee:
                    logging.error(f"Retry -1111 failed: {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            # Handle -4061: position mode error
            if '"code":-4061' in txt or "-4061" in txt:
                logging.info("-4061: re-detecting position mode and retrying once...")
                try:
                    real_hedge = self.detect_position_mode()
                    self.is_hedge_mode = real_hedge
                    p2 = dict(params)
                    if real_hedge:
                        side_hint = 'LONG' if config.strategy_side == 'LONG_ONLY' else 'SHORT'
                        p2['positionSide'] = side_hint
                        p2.pop('reduceOnly', None)
                    else:
                        p2.pop('positionSide', None)
                        if is_open:
                            p2.pop('reduceOnly', None)
                        else:
                            p2['reduceOnly'] = 'true'
                    p2['timestamp'] = ts_ms()
                    p2['recvWindow'] = 15000
                    return _do(p2).json()
                except Exception as ee:
                    logging.error(f"Retry -4061 failed: {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            try:
                clean = {k: v for k, v in params.items() if k not in ("signature", "recvWindow", "timestamp")}
                send_telegram_message(f"❌ *ORDER ERROR*\n{txt}\nParams: `{clean}`")
            except Exception:
                pass
            raise

    def clamp_price(self, p: float) -> float:
        """Round price to valid increment."""
        return _round_to_step_float(p, self.tick_size, mode=ROUND_DOWN)

    def clamp_qty(self, q: float) -> float:
        """Round quantity to valid increment."""
        q = max(q, self.min_qty)
        return _round_to_step_float(q, self.step_size, mode=ROUND_DOWN)

    def market_buy(self, qty: float) -> dict:
        """Place market buy order."""
        if config.dry_run:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}

        side_to_open = 'BUY' if config.strategy_side == 'LONG_ONLY' else 'SELL'
        position_side = 'LONG' if config.strategy_side == 'LONG_ONLY' else 'SHORT'
        qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
        
        params = {
            'symbol': config.symbol,
            'side': side_to_open,
            'type': 'MARKET',
            'quantity': qty_str,
        }
        
        if self.is_hedge_mode:
            params['positionSide'] = position_side
            
        return self.futures_order(params, is_open=True)

    def market_sell(self, qty: float) -> dict:
        """Place market sell order."""
        if config.dry_run:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}

        side_to_close = 'SELL' if config.strategy_side == 'LONG_ONLY' else 'BUY'
        position_side = 'LONG' if config.strategy_side == 'LONG_ONLY' else 'SHORT'
        qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
        
        params = {
            'symbol': config.symbol,
            'side': side_to_close,
            'type': 'MARKET',
            'quantity': qty_str,
        }
        
        if self.is_hedge_mode:
            params['positionSide'] = position_side
        else:
            params['reduceOnly'] = 'true'
            
        return self.futures_order(params, is_open=False)