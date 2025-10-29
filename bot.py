# # bot.py — LIVE/Paper trading via Binance Futures Connector
# # גרסה Production Ready: סנכרון זמן, רענון פילטרים, דיוקים, MIN_NOTIONAL, Backoff, Graceful Shutdown
# # + Price Poller (REST) + WS Watchdog + Status line cleanup

# import os, time, json, threading, queue, csv, datetime, requests, math, uuid, signal, traceback
# from typing import Dict, Tuple, List, Optional
# from dotenv import load_dotenv
# import websocket
# import hmac, hashlib
# from urllib.parse import urlencode
# from decimal import Decimal, ROUND_DOWN, ROUND_FLOOR, ROUND_CEILING

# load_dotenv()

# # ===== קונפיג =====
# SYMBOL = os.getenv("SYMBOL", "SOLUSDT").upper()
# STREAM_SYMBOL = SYMBOL.lower()

# GRID_STEP_USD = float(os.getenv("GRID_STEP_USD", "1.0"))
# TAKE_PROFIT_USD = float(os.getenv("TAKE_PROFIT_USD", "1.0"))
# MAX_LADDERS = int(os.getenv("MAX_LADDERS", "20"))
# QTY_PER_LADDER = float(os.getenv("QTY_PER_LADDER", "1.0"))

# MAX_SPREAD_BPS = float(os.getenv("MAX_SPREAD_BPS", "8"))
# INTERVAL_STATUS_SEC = float(os.getenv("INTERVAL_STATUS_SEC", "1.5"))

# CSV_FILE = os.getenv("CSV_FILE", "trades.csv")
# STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

# PING_INTERVAL = 20.0
# RECONNECT_MIN, RECONNECT_MAX = 1.0, 30.0

# API_KEY = os.getenv("BINANCE_API_KEY", "")
# API_SECRET = os.getenv("BINANCE_API_SECRET", "")
# USE_TESTNET = os.getenv("BINANCE_USE_TESTNET", "no").lower() == "yes"
# DRY_RUN = os.getenv("DRY_RUN", "yes").lower() == "yes"
# COPY_TRADE_ASSUMED_BALANCE = float(os.getenv("COPY_TRADE_ASSUMED_BALANCE", "500.0"))

# MAX_DAILY_USDT = float(os.getenv("MAX_DAILY_USDT", "200"))
# TAKER_FEE = float(os.getenv("TAKER_FEE", "0.0005"))  # 5bps ברירת מחדל

# # === טלגרם ===
# TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# # === אסטרטגיה וזיהוי מצב ===
# STRATEGY_SIDE = os.getenv("STRATEGY_SIDE", "LONG_ONLY").upper()  # LONG_ONLY או SHORT_ONLY
# if STRATEGY_SIDE not in ["LONG_ONLY", "SHORT_ONLY"]:
#     print(f"[FATAL] Invalid STRATEGY_SIDE: {STRATEGY_SIDE}. Defaulting to LONG_ONLY.")
#     STRATEGY_SIDE = "LONG_ONLY"

# DESIRED_POSITION_MODE = os.getenv("DESIRED_POSITION_MODE", "").upper()  # "", "HEDGE", "ONEWAY"

# # === מצב בטחונות ===
# MARGIN_MODE = os.getenv("MARGIN_MODE", "ISOLATED").upper()  # CROSSED או ISOLATED
# if MARGIN_MODE not in ["CROSSED", "ISOLATED"]:
#     print(f"[FATAL] Invalid MARGIN_MODE: {MARGIN_MODE}. Defaulting to ISOLATED.")
#     MARGIN_MODE = "ISOLATED"

# # --- קישורי Futures ו-WS ---
# IS_TESTNET_FUT = USE_TESTNET
# FUTURES_HTTP_BASE = "https://testnet.binancefuture.com" if IS_TESTNET_FUT else "https://fapi.binance.com"
# FUTURES_BASE_URL  = f"{FUTURES_HTTP_BASE}/fapi/v1"
# FUTURES_ACCOUNT_URL = f"{FUTURES_HTTP_BASE}/fapi/v2"

# WS_HOST = "stream.binancefuture.com" if IS_TESTNET_FUT else "fstream.binance.com"
# WS_URL  = f"wss://{WS_HOST}/ws/{STREAM_SYMBOL}@bookTicker"

# # ===== מצב (Status) =====
# base_price = 0.0
# positions: List[Dict] = []
# realized_pnl = 0.0
# total_buys = 0
# total_sells = 0
# spent_today = 0.0
# spent_date = "1970-01-01"

# msg_queue: "queue.Queue[Tuple[float,float,float]]" = queue.Queue(maxsize=1000)

# # ===== סנכרון זמן (לפתרון -1021) =====
# _time_offset_ms = 0  # server - local

# def ts_ms() -> int:
#     """החזרת timestamp מסונכרן לשרת (serverTime + offset)."""
#     return int(time.time() * 1000 + _time_offset_ms)

# def sync_server_time():
#     global _time_offset_ms
#     try:
#         url = f"{FUTURES_BASE_URL}/time"
#         r = requests.get(url, timeout=5)
#         r.raise_for_status()
#         server_time = int(r.json().get("serverTime", 0))
#         local_time = int(time.time() * 1000)
#         _time_offset_ms = server_time - local_time
#         print(f"[TIME] server-local offset: {_time_offset_ms} ms")
#     except Exception as e:
#         print(f"[WARN] time sync failed: {e}")

# # ===== רענון מחיר — ENV =====
# PRICE_REFRESH_SEC = float(os.getenv("PRICE_REFRESH_SEC", "1.0"))  # מרווח פולים ב-REST
# STALE_WS_SEC = float(os.getenv("STALE_WS_SEC", "10"))             # כמה שניות בלי טיקים עד שנחשב סטלי

# # ===== טלגרם (שליחה לא-חוסמת) =====
# def send_telegram_message(message: str):
#     if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
#         return
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}

#     def _send_sync():
#         try:
#             requests.post(url, data=payload, timeout=5)
#         except Exception as e:
#             print(f"\n[TELEGRAM ERROR] {e}")

#     threading.Thread(target=_send_sync, daemon=True).start()

# # ===== CSV =====
# def init_csv():
#     new = not os.path.exists(CSV_FILE)
#     with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
#         w = csv.writer(f)
#         if new:
#             w.writerow(["time","side","price","qty","pnl","total_pnl","bid","ask","spread_bps","note"])

# def log_trade(side: str, price: float, qty: float, pnl: float, total: float,
#               bid: float, ask: float, spread_bps_val: float, note: str = ""):
#     with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
#         csv.writer(f).writerow([
#             datetime.datetime.now().isoformat(timespec="seconds"),
#             side, f"{price:.4f}", f"{qty:.6f}", f"{pnl:.4f}", f"{total:.4f}",
#             f"{bid:.4f}", f"{ask:.4f}", f"{spread_bps_val:.3f}", note
#         ])

# # ===== Persistence =====
# def save_state():
#     state = {
#         "base_price": base_price,
#         "positions": positions,
#         "realized_pnl": realized_pnl,
#         "total_buys": total_buys,
#         "total_sells": total_sells,
#         "spent_today": spent_today,
#         "spent_date": spent_date,
#     }
#     tmp = STATE_FILE + ".tmp"
#     with open(tmp, "w") as f:
#         json.dump(state, f, indent=4)
#     os.replace(tmp, STATE_FILE)

# def load_state():
#     global base_price, positions, realized_pnl, total_buys, total_sells, spent_today, spent_date
#     if os.path.exists(STATE_FILE):
#         with open(STATE_FILE, "r") as f:
#             try:
#                 state = json.load(f)
#                 base_price = state.get("base_price", base_price)
#                 positions = state.get("positions", positions)
#                 realized_pnl = state.get("realized_pnl", realized_pnl)
#                 total_buys = state.get("total_buys", total_buys)
#                 total_sells = state.get("total_sells", total_sells)
#                 spent_today = state.get("spent_today", spent_today)
#                 spent_date = state.get("spent_date", spent_date)

#                 current_date = datetime.datetime.now().strftime("%Y-%m-%d")
#                 if current_date != spent_date:
#                     print(f"[INFO] Daily spent reset during load ({spent_date} -> {current_date}).")
#                     spent_today = 0.0
#                     spent_date = current_date

#                 print(f"[STATE] Loaded state from {STATE_FILE}. Open positions: {len(positions)}")
#                 return True
#             except Exception as e:
#                 print(f"[WARNING] Failed to load state: {e}. Starting fresh.")
#                 return False
#     return False

# # ===== Helpers =====
# def spread_bps(bid: float, ask: float) -> float:
#     if ask <= 0: return 9999.0
#     return (ask - bid) / ask * 10_000

# def request_with_retry(method: str, url: str, *, headers=None, data=None, params=None, timeout=5.0, retries=3):
#     delay = 0.5
#     for i in range(retries):
#         try:
#             r = requests.request(method, url, headers=headers, data=data, params=params, timeout=timeout)
#             r.raise_for_status()
#             return r
#         except requests.exceptions.HTTPError as e:
#             ra = e.response.headers.get("Retry-After")
#             if ra:
#                 try:
#                     wait = max(float(ra), delay)
#                 except:
#                     wait = delay
#             else:
#                 wait = delay
#             if i == retries - 1:
#                 raise
#             if i == 0:
#                 print(f"[HTTP RETRY] {method} {url} failed ({e.response.status_code}). Retrying...")
#             time.sleep(wait)
#             delay = min(delay * 2, 8.0)
#         except requests.exceptions.RequestException as e:
#             if i == retries - 1:
#                 raise
#             if i == 0:
#                 print(f"[HTTP RETRY] {method} {url} failed ({e.__class__.__name__}). Retrying...")
#             time.sleep(delay)
#             delay = min(delay * 2, 8.0)

# # שימוש ב-Futures endpoint
# def get_initial_book(symbol: str) -> Tuple[float,float,float]:
#     url = f"{FUTURES_BASE_URL}/ticker/bookTicker"
#     r = request_with_retry('GET', url, params={"symbol": symbol})
#     d = r.json()
#     bid, ask = float(d["bidPrice"]), float(d["askPrice"])
#     mid = (bid + ask) / 2.0
#     return bid, ask, mid

# def sign_request(params: dict) -> str:
#     query_string = urlencode(params, True)
#     signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
#     return f"{query_string}&signature={signature}"

# def _futures_exchange_info(symbol: str):
#     url = f"{FUTURES_BASE_URL}/exchangeInfo"
#     r = request_with_retry('GET', url, params={"symbol": symbol})
#     j = r.json()
#     return j["symbols"][0]

# # יישור מחיר לבסיס הגריד (דינמי לפי צד)
# def align_to_grid(mid: float, step: float, mode: str) -> float:
#     if step <= 0: return mid
#     dm = Decimal(str(mid))
#     ds = Decimal(str(step))
#     rounding_mode = ROUND_FLOOR if mode == 'LONG_ONLY' else ROUND_CEILING
#     num_steps = (dm / ds)
#     aligned = num_steps.to_integral_value(rounding=rounding_mode) * ds
#     return float(aligned)

# # עיגול/כימות לערכי צעד כמחרוזת מדויקת
# def _decimal_places(step: float) -> int:
#     ds = Decimal(str(step)).normalize()
#     return -ds.as_tuple().exponent if ds.as_tuple().exponent < 0 else 0

# def _format_to_step(x: float, step: float, mode=ROUND_DOWN) -> str:
#     dx = Decimal(str(x))
#     ds = Decimal(str(step))
#     q = (dx / ds).to_integral_value(rounding=mode) * ds
#     exp = _decimal_places(step)
#     return format(q, f".{exp}f")

# def _round_to_step_float(x: float, step: float, mode=ROUND_DOWN) -> float:
#     return float(_format_to_step(x, step, mode=mode))

# # ===== Broker =====
# class Broker:
#     def __init__(self):
#         if DRY_RUN:
#             self.is_hedge_mode = False
#             self.step_size = 0.1
#             self.tick_size = 0.01
#             self.min_qty = 0.1
#             self.min_notional = 5.0
#             self.qty_prec = _decimal_places(self.step_size)
#             self.price_prec = _decimal_places(self.tick_size)
#             return

#         try:
#             sym = _futures_exchange_info(SYMBOL)
#         except Exception as e:
#             print(f"[WARN] exchangeInfo failed, using hardcoded defaults. {e}")
#             sym = {"filters":[
#                 {"filterType":"PRICE_FILTER","tickSize":"0.01"},
#                 {"filterType":"LOT_SIZE","stepSize":"0.1","minQty":"0.1"},
#                 {"filterType":"MIN_NOTIONAL","notional":"5.0"}
#             ]}
#         def get_filter(ft):
#             for f in sym.get("filters", []):
#                 if f.get("filterType") == ft:
#                     return f
#             return {}
#         price_f   = get_filter("PRICE_FILTER")
#         lot_f     = get_filter("LOT_SIZE")
#         notional_f= get_filter("MIN_NOTIONAL")

#         self.tick_size = float(price_f.get("tickSize", "0.01"))
#         self.step_size = float(lot_f.get("stepSize",  "0.1"))
#         self.min_qty   = float(lot_f.get("minQty",    "0.1"))
#         self.min_notional = float(notional_f.get("notional", "5.0"))

#         self.price_prec = _decimal_places(self.tick_size)
#         self.qty_prec   = _decimal_places(self.step_size)

#         self.is_hedge_mode = self.detect_position_mode()

#         if DESIRED_POSITION_MODE in ("HEDGE", "ONEWAY"):
#             want_hedge = (DESIRED_POSITION_MODE == "HEDGE")
#             if want_hedge != self.is_hedge_mode:
#                 ok = self.set_position_mode(want_hedge)
#                 if ok:
#                     self.is_hedge_mode = want_hedge
#                 else:
#                     send_telegram_message(
#                         f"⚠️ Failed to set position mode to {DESIRED_POSITION_MODE}. "
#                         f"Remain: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}*."
#                     )

#         if MARGIN_MODE != "ISOLATED":
#             self.set_margin_mode(MARGIN_MODE)

#         send_telegram_message(f"ℹ️ Position mode: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}* | Margin: *{MARGIN_MODE}*")

#     # === רענון פילטרים ===
#     def refresh_symbol_filters(self):
#         try:
#             sym = _futures_exchange_info(SYMBOL)
#             def get_filter(ft):
#                 for f in sym.get("filters", []):
#                     if f.get("filterType") == ft:
#                         return f
#                 return {}
#             price_f   = get_filter("PRICE_FILTER")
#             lot_f     = get_filter("LOT_SIZE")
#             notional_f= get_filter("MIN_NOTIONAL")

#             self.tick_size = float(price_f.get("tickSize", self.tick_size))
#             self.step_size = float(lot_f.get("stepSize",  self.step_size))
#             self.min_qty   = float(lot_f.get("minQty",    self.min_qty))
#             self.min_notional = float(notional_f.get("notional", self.min_notional))

#             self.price_prec = _decimal_places(self.tick_size)
#             self.qty_prec   = _decimal_places(self.step_size)
#         except Exception as e:
#             print(f"[WARN] refresh_symbol_filters failed: {e}")

#     # ---- Margin Mode ----
#     def set_margin_mode(self, margin_type: str) -> bool:
#         try:
#             params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'symbol': SYMBOL, 'marginType': margin_type}
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
#             url = f"{FUTURES_BASE_URL}/marginType"
#             request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
#             send_telegram_message(f"✅ *Margin mode set to {margin_type}*")
#             return True
#         except Exception as e:
#             err_text = getattr(e, 'response', None) and getattr(e.response, 'text', str(e))
#             print(f"[WARN] set_margin_mode failed: {err_text}")
#             send_telegram_message(f"⚠️ Failed to set margin mode to {margin_type}. "
#                                   f"סיבות נפוצות: פוזיציות/פקודות פתוחות או שכבר במצב המבוקש.\n{err_text}")
#             return False

#     # ---- Position Mode ----
#     def detect_position_mode(self) -> bool:
#         """True = Hedge, False = One-way."""
#         try:
#             params = {'timestamp': ts_ms(), 'recvWindow': 15000}
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY}
#             url = f"{FUTURES_BASE_URL}/positionSide/dual?{signed}"
#             r = request_with_retry('GET', url, headers=headers)
#             d = r.json()
#             return bool(d.get("dualSidePosition", False))
#         except Exception as e:
#             print(f"[WARN] detect_position_mode failed: {e}. Assuming One-way.")
#             return False

#     def set_position_mode(self, want_hedge: bool) -> bool:
#         try:
#             params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'dualSidePosition': 'true' if want_hedge else 'false'}
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
#             url = f"{FUTURES_BASE_URL}/positionSide/dual"
#             request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
#             return True
#         except Exception as e:
#             print(f"[WARN] set_position_mode failed: {e}")
#             return False

#     # ---- Live positions ----
#     def _fetch_live_positions(self, symbol: str) -> Dict[str, float]:
#         if DRY_RUN:
#             wanted_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
#             return {wanted_side: sum(p['qty'] for p in positions)}
#         try:
#             params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'symbol': symbol}
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY}
#             url = f"{FUTURES_ACCOUNT_URL}/positionRisk?{signed}"
#             r = request_with_retry('GET', url, headers=headers)
#             arr = r.json()
#             live_q = {"LONG": 0.0, "SHORT": 0.0, "BOTH": 0.0}
#             if not isinstance(arr, list):
#                 arr = [arr]
#             for p in arr:
#                 if p.get('symbol') != symbol:
#                     continue
#                 ps = p.get('positionSide', 'BOTH')
#                 size = float(p.get('positionAmt', 0.0) or 0.0)
#                 live_q[ps] = max(live_q.get(ps, 0.0), abs(size))
#             return live_q
#         except Exception as e:
#             print(f"[WARN] _fetch_live_positions failed: {e}")
#             return {}

#     def get_position_qty(self, symbol: str, side: str, live_positions: Dict[str, float]) -> float:
#         if not live_positions: return 0.0
#         if self.is_hedge_mode:
#             return live_positions.get(side, 0.0)
#         return live_positions.get('BOTH', 0.0)

#     # ---- Orders (עם טיפול -1021/-1111/-4061) ----
#     def futures_order(self, params: dict, is_open: bool) -> dict:
#         def _do(params):
#             params = dict(params)
#             params.setdefault('timestamp', ts_ms())
#             params.setdefault('recvWindow', 15000)
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
#             url = f"{FUTURES_BASE_URL}/order"
#             r = request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
#             return r

#         try:
#             return _do(params).json()
#         except requests.exceptions.HTTPError as e:
#             txt = (e.response.text or "")

#             if '"code":-1021' in txt or "-1021" in txt:
#                 print("[INFO] -1021: syncing server time and retrying once...")
#                 sync_server_time()
#                 try:
#                     p2 = dict(params)
#                     p2['timestamp'] = ts_ms()
#                     p2['recvWindow'] = 15000
#                     return _do(p2).json()
#                 except Exception as ee:
#                     print(f"[RETRY -1021 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

#             if '"code":-1111' in txt or "-1111" in txt:
#                 print("[INFO] -1111: refreshing filters + reclamp qty/price and retrying once...")
#                 try:
#                     self.refresh_symbol_filters()
#                     p2 = dict(params)
#                     if 'quantity' in p2:
#                         qf = float(p2['quantity'])
#                         p2['quantity'] = _format_to_step(qf, self.step_size, mode=ROUND_DOWN)
#                     if 'price' in p2:
#                         pf = float(p2['price'])
#                         p2['price'] = _format_to_step(pf, self.tick_size, mode=ROUND_DOWN)
#                     p2['timestamp']  = ts_ms()
#                     p2['recvWindow'] = 15000
#                     return _do(p2).json()
#                 except Exception as ee:
#                     print(f"[RETRY -1111 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

#             if '"code":-4061' in txt or "-4061" in txt:
#                 print("[INFO] -4061: re-detecting position mode and retrying once...")
#                 try:
#                     real_hedge = self.detect_position_mode()
#                     self.is_hedge_mode = real_hedge
#                     p2 = dict(params)
#                     if real_hedge:
#                         side_hint = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
#                         p2['positionSide'] = side_hint
#                         p2.pop('reduceOnly', None)
#                     else:
#                         p2.pop('positionSide', None)
#                         if is_open:
#                             p2.pop('reduceOnly', None)
#                         else:
#                             p2['reduceOnly'] = 'true'
#                     p2['timestamp']  = ts_ms()
#                     p2['recvWindow'] = 15000
#                     return _do(p2).json()
#                 except Exception as ee:
#                     print(f"[RETRY -4061 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

#             try:
#                 clean = {k: v for k, v in params.items() if k not in ("signature", "recvWindow", "timestamp")}
#                 send_telegram_message(f"❌ *ORDER ERROR*\n{txt}\nParams: `{clean}`")
#             except Exception:
#                 pass
#             raise

#     def clamp_price(self, p: float) -> float:
#         return _round_to_step_float(p, self.tick_size, mode=ROUND_DOWN)

#     def clamp_qty(self, q: float) -> float:
#         q = max(q, self.min_qty)
#         return _round_to_step_float(q, self.step_size, mode=ROUND_DOWN)

#     def balance_usdt(self) -> float:
#         if DRY_RUN:
#             return 999999.0
#         try:
#             params = {'timestamp': ts_ms(), 'recvWindow': 15000}
#             signed = sign_request(params)
#             headers = {'X-MBX-APIKEY': API_KEY}
#             url = f"{FUTURES_ACCOUNT_URL}/balance?{signed}"
#             r = request_with_retry('GET', url, headers=headers)
#             bal = r.json()
#             for b in bal:
#                 if b.get("asset") == "USDT":
#                     return float(b.get("availableBalance", 0.0))
#             return 0.0
#         except requests.exceptions.HTTPError as e:
#             if e.response.status_code == 401:
#                 return COPY_TRADE_ASSUMED_BALANCE
#             return 0.0
#         except Exception:
#             return 0.0

#     def market_buy(self, qty: float) -> dict:
#         if DRY_RUN:
#             return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
#         side_to_open = 'BUY' if STRATEGY_SIDE == 'LONG_ONLY' else 'SELL'
#         position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
#         qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
#         params = {
#             'symbol': SYMBOL,
#             'side': side_to_open,
#             'type': 'MARKET',
#             'quantity': qty_str,
#         }
#         if self.is_hedge_mode:
#             params['positionSide'] = position_side
#         return self.futures_order(params, is_open=True)

#     def market_sell(self, qty: float) -> dict:
#         if DRY_RUN:
#             return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
#         side_to_close = 'SELL' if STRATEGY_SIDE == 'LONG_ONLY' else 'BUY'
#         position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
#         qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
#         params = {
#             'symbol': SYMBOL,
#             'side': side_to_close,
#             'type': 'MARKET',
#             'quantity': qty_str,
#         }
#         if self.is_hedge_mode:
#             params['positionSide'] = position_side
#         else:
#             params['reduceOnly'] = 'true'
#         return self.futures_order(params, is_open=False)

# broker: Optional[Broker] = None

# # ===== רענון מחירים — כלי עזר =====
# last_tick_time = 0.0        # מתי נכנס טיק לאחרונה (WS או REST)
# _last_status_len = 0        # אורך שורת הסטטוס הקודמת (לניקוי יפה בקונסול)

# def enqueue_quote(bid: float, ask: float):
#     """דוחף עדכון מחיר לתור ומעדכן חותמת זמן אחרונה."""
#     global last_tick_time
#     try:
#         mid = (bid + ask) / 2.0
#         msg_queue.put_nowait((bid, ask, mid))
#         last_tick_time = time.time()
#     except Exception:
#         pass

# # ===== לוגיקת גריד =====
# def _ensure_min_notional_and_cap(trade_price: float, qty: float) -> Optional[Tuple[float, float]]:

#     qty = broker.clamp_qty(qty)
#     notional = trade_price * qty

#     if broker.min_notional and notional < broker.min_notional:
#         required = broker.min_notional + broker.tick_size
#         req_qty = required / trade_price
#         req_qty = broker.clamp_qty(req_qty)
#         est_cost = trade_price * req_qty
#         if spent_today + est_cost > MAX_DAILY_USDT:
#             return None
#         if req_qty <= 0:
#             return None
#         return req_qty, est_cost

#     est_cost = trade_price * qty
#     if spent_today + est_cost > MAX_DAILY_USDT:
#         return None
#     return qty, est_cost

# def maybe_enter(bid: float, ask: float):
#     global positions, total_buys, spent_today
#     if len(positions) >= MAX_LADDERS:
#         return

#     is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")
#     position_side = 'LONG' if is_long_strategy else 'SHORT'

#     if is_long_strategy:
#         next_level = base_price - GRID_STEP_USD * (len(positions) + 1)
#         position_trigger = (ask <= next_level)
#         trade_price = ask
#     else:
#         next_level = base_price + GRID_STEP_USD * (len(positions) + 1)
#         position_trigger = (bid >= next_level)
#         trade_price = bid

#     if position_trigger:
#         ensured = _ensure_min_notional_and_cap(trade_price, QTY_PER_LADDER)
#         if ensured is None:
#             log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask), "MinNotional/DailyCap")
#             return

#         qty, est_cost = ensured

#         if not DRY_RUN and broker.balance_usdt() < est_cost * 1.02:
#             log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask),
#                       f"No USDT. Assuming balance: ${COPY_TRADE_ASSUMED_BALANCE:.2f}")
#             return

#         try:
#             order = broker.market_buy(qty)
#             total_buys += 1
#             spent_today += 0 if DRY_RUN else est_cost
#             positions.append({"entry": trade_price, "qty": float(qty), "buyId": order.get("orderId", "n/a")})
#             sp = spread_bps(bid, ask)

#             tg_msg = (
#                 f"🚀 *GRID OPEN: {STRATEGY_SIDE}*\n"
#                 f"----------------------------\n"
#                 f"💰 {SYMBOL} @ {trade_price:.4f}\n"
#                 f"📐 Qty: {qty:.4f}\n"
#                 f"🏷️ Order ID: {order.get('orderId', 'n/a')}"
#             )
#             send_telegram_message(tg_msg)

#             print(f"\n[ENTER {STRATEGY_SIDE}] qty={qty} @ ~{trade_price:.4f} | open={len(positions)} | spread={sp:.2f}bps | orderId={order.get('orderId','n/a')}")
#             log_trade(f"OPEN_{position_side}", trade_price, float(qty), 0.0, realized_pnl, bid, ask, sp, f"orderId={order.get('orderId','n/a')}")
#             save_state()
#         except requests.exceptions.HTTPError as e:
#             print(f"\n[OPEN HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
#             log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
#             send_telegram_message(f"❌ *OPEN ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code}\n{e.response.text}")
#         except Exception as e:
#             traceback.print_exc()
#             print(f"\n[OPEN ERROR] {e}")
#             log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
#             send_telegram_message(f"🔥 *CRITICAL OPEN ERROR ({STRATEGY_SIDE})*\n{e}")

# def maybe_exit(bid: float, ask: float):
#     global positions, realized_pnl, total_sells

#     is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")
#     exit_price = bid if is_long_strategy else ask

#     live_positions = broker._fetch_live_positions(SYMBOL)

#     remaining = []
#     for p in positions:
#         if is_long_strategy:
#             target = p["entry"] + TAKE_PROFIT_USD
#             exit_condition = (exit_price >= target)
#             side_log = "CLOSE_LONG"
#             pos_side = 'LONG'
#         else:
#             target = p["entry"] - TAKE_PROFIT_USD
#             exit_condition = (exit_price <= target)
#             side_log = "CLOSE_SHORT"
#             pos_side = 'SHORT'

#         if exit_condition:
#             live_qty = broker.get_position_qty(SYMBOL, pos_side, live_positions)
#             if live_qty <= 0:
#                 remaining.append(p)
#                 continue

#             qty_to_close = broker.clamp_qty(min(p["qty"], live_qty))
#             try:
#                 order = broker.market_sell(qty_to_close)

#                 if is_long_strategy:
#                     pnl = (exit_price - p["entry"]) * float(qty_to_close)
#                 else:
#                     pnl = (p["entry"] - exit_price) * float(qty_to_close)

#                 fee_open  = p["entry"] * qty_to_close * TAKER_FEE
#                 fee_close = exit_price * qty_to_close * TAKER_FEE
#                 pnl -= (fee_open + fee_close)

#                 realized_pnl += pnl
#                 total_sells += 1
#                 sp = spread_bps(bid, ask)

#                 tg_msg = (
#                     f"✅ *GRID CLOSE: {STRATEGY_SIDE}*\n"
#                     f"-------------------------------\n"
#                     f"💸 PnL: *+${pnl:.2f}* (Total: ${realized_pnl:.2f})\n"
#                     f"💰 Entry @ {p['entry']:.4f}\n"
#                     f"💵 Exit @ {exit_price:.4f}\n"
#                     f"💳 Fee: ${(fee_open + fee_close):.4f}"
#                 )
#                 send_telegram_message(tg_msg)

#                 print(f"\n[EXIT {STRATEGY_SIDE}] qty={qty_to_close} @ ~{exit_price:.4f} | entry={p['entry']:.4f} | PnL=+${pnl:.2f} | total=${realized_pnl:.2f} | orderId={order.get('orderId','n/a')}")
#                 log_trade(side_log, exit_price, float(qty_to_close), pnl, realized_pnl, bid, ask, sp, f"orderId={order.get('orderId','n/a')}")
#                 save_state()

#                 remaining_qty = float(p["qty"]) - float(qty_to_close)
#                 if remaining_qty > 0:
#                     p2 = dict(p)
#                     p2["qty"] = remaining_qty
#                     remaining.append(p2)
#             except requests.exceptions.HTTPError as e:
#                 print(f"\n[CLOSE HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
#                 log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
#                 send_telegram_message(f"❌ *CLOSE ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code}\n{e.response.text}")
#                 remaining.append(p)
#             except Exception as e:
#                 traceback.print_exc()
#                 print(f"\n[CLOSE ERROR] {e}")
#                 log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
#                 send_telegram_message(f"🔥 *CRITICAL CLOSE ERROR ({STRATEGY_SIDE})*\n{e}")
#                 remaining.append(p)
#         else:
#             remaining.append(p)

#     positions[:] = remaining

# # ===== Processor =====
# def processor(stop_evt: threading.Event):
#     global base_price
#     last_status = 0.0
#     while not stop_evt.is_set():
#         curr = datetime.datetime.now().strftime("%Y-%m-%d")
#         global spent_date, spent_today
#         if curr != spent_date:
#             print(f"\n[INFO] Daily spent reset ({spent_date} -> {curr}).")
#             spent_today = 0.0
#             spent_date = curr
#             save_state()

#         try:
#             bid, ask, mid = msg_queue.get(timeout=1.0)
#         except queue.Empty:
#             continue

#         sp = spread_bps(bid, ask)
#         if sp > MAX_SPREAD_BPS:
#             nowt = time.time()
#             if nowt - last_status > INTERVAL_STATUS_SEC:
#                 status = f"Spread {sp:.2f}bps too wide, waiting..."
#                 global _last_status_len
#                 pad = max(0, _last_status_len - len(status))
#                 print("\r" + status + (" " * pad), end="", flush=True)
#                 _last_status_len = len(status)
#                 last_status = nowt
#             continue

#         is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")

#         if is_long_strategy and mid < base_price:
#             maybe_enter(bid, ask)
#         elif not is_long_strategy and mid > base_price:
#             maybe_enter(bid, ask)

#         if positions:
#             maybe_exit(bid, ask)

#         # עדכון base_price רק כשאין פוזיציות
#         if not positions and abs(mid - base_price) >= GRID_STEP_USD:
#             base_price = align_to_grid(mid, GRID_STEP_USD, STRATEGY_SIDE)
#             save_state()

#         now = time.time()
#         if now - last_status > INTERVAL_STATUS_SEC:
#             status = (
#                 f"Mid={mid:.4f} | Bid={bid:.4f} Ask={ask:.4f} | Spread={sp:.2f}bps | Base={base_price:.0f} | "
#                 f"Open={len(positions)} | Buys={total_buys} Sells={total_sells} | Realized=${realized_pnl:.2f} | "
#                 f"SpentToday=${spent_today:.2f} ({STRATEGY_SIDE})"
#             )
#             global _last_status_len
#             pad = max(0, _last_status_len - len(status))
#             print("\r" + status + (" " * pad), end="", flush=True)
#             _last_status_len = len(status)
#             last_status = now

# # ===== Price Poller (REST) + WS Watchdog =====
# class PricePoller:
#     def __init__(self, interval_sec: float):
#         self.interval = max(0.3, interval_sec)
#         self.stop_evt = threading.Event()
#         self.thread: Optional[threading.Thread] = None

#     def start(self):
#         self.thread = threading.Thread(target=self.run, daemon=True)
#         self.thread.start()

#     def stop(self):
#         self.stop_evt.set()
#         if self.thread:
#             self.thread.join(timeout=3)

#     def run(self):
#         backoff = 0.0
#         while not self.stop_evt.is_set():
#             try:
#                 stale = (time.time() - last_tick_time) > STALE_WS_SEC if last_tick_time else True
#                 if stale:
#                     bid, ask, _ = get_initial_book(SYMBOL)
#                     enqueue_quote(bid, ask)
#             except Exception:
#                 backoff = min(backoff + 0.2, 2.0)
#             else:
#                 backoff = 0.0
#             time.sleep(self.interval + backoff)

# # ===== WebSocket =====
# class WSClient:
#     def __init__(self, url: str):
#         self.url = url
#         self.ws: Optional[websocket.WebSocketApp] = None
#         self.thread: Optional[threading.Thread] = None
#         self.stop_evt = threading.Event()
#         self.reconnect_delay = RECONNECT_MIN

#     def on_open(self, ws):
#         print("\n[WS] Connected.")
#         self.reconnect_delay = RECONNECT_MIN

#     def on_message(self, ws, msg):
#         try:
#             d = json.loads(msg)
#             bid, ask = float(d["b"]), float(d["a"])
#             enqueue_quote(bid, ask)
#         except Exception:
#             pass

#     def on_error(self, ws, err):
#         print(f"\n[WS] Error: {err}")

#     def on_close(self, ws, code, msg):
#         print(f"\n[WS] Closed: {code} {msg}")

#     def run_forever(self):
#         while not self.stop_evt.is_set():
#             self.ws = websocket.WebSocketApp(
#                 self.url, on_open=self.on_open, on_message=self.on_message,
#                 on_error=self.on_error, on_close=self.on_close
#             )
#             self.ws.run_forever(ping_interval=PING_INTERVAL, ping_timeout=10)
#             if self.stop_evt.is_set(): break
#             delay = min(self.reconnect_delay, RECONNECT_MAX)
#             print(f"[WS] Reconnecting in {delay:.1f}s...")
#             time.sleep(delay)
#             self.reconnect_delay = min(self.reconnect_delay * 2, RECONNECT_MAX)

#     def start(self):
#         self.thread = threading.Thread(target=self.run_forever, daemon=True)
#         self.thread.start()

#     def stop(self):
#         self.stop_evt.set()
#         try:
#             if self.ws:
#                 self.ws.close()
#         except Exception:
#             pass
#         if self.thread:
#             self.thread.join(timeout=3)

# # ===== main + Graceful Shutdown =====
# stop_evt = threading.Event()
# ws_client: Optional[WSClient] = None
# proc_thread: Optional[threading.Thread] = None
# price_poller: Optional[PricePoller] = None  # <- poller גלובלי

# def _graceful_exit(signum, frame):
#     print(f"\n[Signal {signum}] Graceful shutdown...")
#     try:
#         save_state()
#     except Exception:
#         pass
#     try:
#         if ws_client:
#             ws_client.stop()
#     except Exception:
#         pass
#     try:
#         if price_poller:
#             price_poller.stop()
#     except Exception:
#         pass
#     try:
#         stop_evt.set()
#         if proc_thread:
#             proc_thread.join(timeout=3)
#     except Exception:
#         pass
#     print("Bye!")
#     os._exit(0)

# signal.signal(signal.SIGINT, _graceful_exit)
# signal.signal(signal.SIGTERM, _graceful_exit)

# def main():
#     global base_price, broker, ws_client, proc_thread, price_poller

#     print(f"Starting SOL bot on {SYMBOL} | Mode={'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')}")
#     sync_server_time()

#     try:
#         broker = Broker()
#     except Exception as e:
#         print(f"[FATAL] Broker initialization failed: {e}")
#         traceback.print_exc()
#         return

#     print("Broker ready.")

#     state_loaded = load_state()

#     if not state_loaded:
#         global spent_date
#         spent_date = datetime.datetime.now().strftime("%Y-%m-%d")
#         try:
#             bid, ask, mid = get_initial_book(SYMBOL)
#         except Exception:
#             mid = 200.0
#             bid, ask = mid - 0.01, mid + 0.01
#         base_price = align_to_grid(mid, GRID_STEP_USD, STRATEGY_SIDE)
#         # הזנת מדידה ראשונה כדי שה-processor יתחיל לרוץ
#         enqueue_quote(bid, ask)

#     print(f"Base price (rounded): {base_price:.0f}")
#     print(f"[STRATEGY] Current strategy: {STRATEGY_SIDE}")

#     init_csv()

#     proc_thread = threading.Thread(target=processor, args=(stop_evt,), daemon=True)
#     proc_thread.start()

#     ws_client = WSClient(WS_URL)
#     ws_client.start()

#     # הפעלת הפולר (REST) — דואג שלא ניתקע על מחיר סטטי גם אם ה-WS שקט
#     price_poller = PricePoller(PRICE_REFRESH_SEC)
#     price_poller.start()

#     try:
#         while True:
#             time.sleep(0.5)
#     except KeyboardInterrupt:
#         _graceful_exit(2, None)

# if __name__ == "__main__":
#     main()



import os, time, json, threading, queue, csv, datetime, requests, math, uuid, signal, traceback
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv
import websocket
import hmac, hashlib
from urllib.parse import urlencode
from decimal import Decimal, ROUND_DOWN, ROUND_FLOOR, ROUND_CEILING

load_dotenv()

# ===== קונפיג =====
SYMBOL = os.getenv("SYMBOL", "SOLUSDT").upper()
STREAM_SYMBOL = SYMBOL.lower()

GRID_STEP_USD = float(os.getenv("GRID_STEP_USD", "1.0"))
TAKE_PROFIT_USD = float(os.getenv("TAKE_PROFIT_USD", "1.0"))
MAX_LADDERS = int(os.getenv("MAX_LADDERS", "20"))
QTY_PER_LADDER = float(os.getenv("QTY_PER_LADDER", "1.0"))

MAX_SPREAD_BPS = float(os.getenv("MAX_SPREAD_BPS", "8"))
INTERVAL_STATUS_SEC = float(os.getenv("INTERVAL_STATUS_SEC", "1.5"))

CSV_FILE = os.getenv("CSV_FILE", "trades.csv")
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

# --- הגדרות סנכרון משופרות (לתיקון חוסר סנכרון) ---
PING_INTERVAL = float(os.getenv("PING_INTERVAL", "10.0"))
PING_TIMEOUT = float(os.getenv("PING_TIMEOUT", "5.0"))
RECONNECT_MIN, RECONNECT_MAX = 1.0, 30.0

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("BINANCE_USE_TESTNET", "no").lower() == "yes"
DRY_RUN = os.getenv("DRY_RUN", "yes").lower() == "yes"
COPY_TRADE_ASSUMED_BALANCE = float(os.getenv("COPY_TRADE_ASSUMED_BALANCE", "500.0"))

MAX_DAILY_USDT = float(os.getenv("MAX_DAILY_USDT", "200"))
TAKER_FEE = float(os.getenv("TAKER_FEE", "0.0005"))

# === טלגרם ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === אסטרטגיה וזיהוי מצב ===
STRATEGY_SIDE = os.getenv("STRATEGY_SIDE", "LONG_ONLY").upper()
if STRATEGY_SIDE not in ["LONG_ONLY", "SHORT_ONLY"]:
    print(f"[FATAL] Invalid STRATEGY_SIDE: {STRATEGY_SIDE}. Defaulting to LONG_ONLY.")
    STRATEGY_SIDE = "LONG_ONLY"

DESIRED_POSITION_MODE = os.getenv("DESIRED_POSITION_MODE", "").upper()

# === מצב בטחונות ===
MARGIN_MODE = os.getenv("MARGIN_MODE", "ISOLATED").upper()
if MARGIN_MODE not in ["CROSSED", "ISOLATED"]:
    print(f"[FATAL] Invalid MARGIN_MODE: {MARGIN_MODE}. Defaulting to ISOLATED.")
    MARGIN_MODE = "ISOLATED"

# --- קישורי Futures ו-WS ---
IS_TESTNET_FUT = USE_TESTNET
FUTURES_HTTP_BASE = "https://testnet.binancefuture.com" if IS_TESTNET_FUT else "https://fapi.binance.com"
FUTURES_BASE_URL = f"{FUTURES_HTTP_BASE}/fapi/v1"
FUTURES_ACCOUNT_URL = f"{FUTURES_HTTP_BASE}/fapi/v2"

WS_HOST = "stream.binancefuture.com" if IS_TESTNET_FUT else "fstream.binance.com"
WS_URL = f"wss://{WS_HOST}/ws/{STREAM_SYMBOL}@bookTicker"

# === רפרוש מחיר רציף (ENV חדש - ערכים משופרים לגיבוי) ===
PRICE_REFRESH_SEC = float(os.getenv("PRICE_REFRESH_SEC", "0.5"))
STALE_WS_SEC = float(os.getenv("STALE_WS_SEC", "5"))

# ===== מצב (Status) =====
base_price = 0.0
positions: List[Dict] = []
realized_pnl = 0.0
total_buys = 0
total_sells = 0
spent_today = 0.0
spent_date = "1970-01-01"

msg_queue: "queue.Queue[Tuple[float,float,float]]" = queue.Queue(maxsize=1000)

# ===== סנכרון זמן (לפתרון -1021) =====
_time_offset_ms = 0

def ts_ms() -> int:
    """החזרת timestamp מסונכרן לשרת (serverTime + offset)."""
    return int(time.time() * 1000 + _time_offset_ms)

def sync_server_time():
    global _time_offset_ms
    try:
        url = f"{FUTURES_BASE_URL}/time"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        server_time = int(r.json().get("serverTime", 0))
        local_time = int(time.time() * 1000)
        _time_offset_ms = server_time - local_time
        print(f"[TIME] server-local offset: {_time_offset_ms} ms")
    except Exception as e:
        print(f"[WARN] time sync failed: {e}")

# ===== טלגרם (שליחה לא-חוסמת) =====
def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}

    def _send_sync():
        try:
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            print(f"\n[TELEGRAM ERROR] {e}")

    threading.Thread(target=_send_sync, daemon=True).start()

# ===== CSV =====
def init_csv():
    new = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time","side","price","qty","pnl","total_pnl","bid","ask","spread_bps","note"])

def log_trade(side: str, price: float, qty: float, pnl: float, total: float,
              bid: float, ask: float, spread_bps_val: float, note: str = ""):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            side, f"{price:.4f}", f"{qty:.6f}", f"{pnl:.4f}", f"{total:.4f}",
            f"{bid:.4f}", f"{ask:.4f}", f"{spread_bps_val:.3f}", note
        ])

# ===== Persistence =====
def save_state():
    state = {
        "base_price": base_price,
        "positions": positions,
        "realized_pnl": realized_pnl,
        "total_buys": total_buys,
        "total_sells": total_sells,
        "spent_today": spent_today,
        "spent_date": spent_date,
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=4)
    os.replace(tmp, STATE_FILE)

def load_state():
    global base_price, positions, realized_pnl, total_buys, total_sells, spent_today, spent_date
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                base_price = state.get("base_price", base_price)
                positions = state.get("positions", positions)
                realized_pnl = state.get("realized_pnl", realized_pnl)
                total_buys = state.get("total_buys", total_buys)
                total_sells = state.get("total_sells", total_sells)
                spent_today = state.get("spent_today", spent_today)
                spent_date = state.get("spent_date", spent_date)

                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                if current_date != spent_date:
                    print(f"[INFO] Daily spent reset during load ({spent_date} -> {current_date}).")
                    spent_today = 0.0
                    spent_date = current_date

                print(f"[STATE] Loaded state from {STATE_FILE}. Open positions: {len(positions)}")
                return True
            except Exception as e:
                print(f"[WARNING] Failed to load state: {e}. Starting fresh.")
                return False
    return False

# ===== Helpers =====
def spread_bps(bid: float, ask: float) -> float:
    if ask <= 0: return 9999.0
    return (ask - bid) / ask * 10_000

def request_with_retry(method: str, url: str, *, headers=None, data=None, params=None, timeout=5.0, retries=3):
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
                print(f"[HTTP RETRY] {method} {url} failed ({e.response.status_code}). Retrying...")
            time.sleep(wait)
            delay = min(delay * 2, 8.0)
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                raise
            if i == 0:
                print(f"[HTTP RETRY] {method} {url} failed ({e.__class__.__name__}). Retrying...")
            time.sleep(delay)
            delay = min(delay * 2, 8.0)

# שימוש ב-Futures endpoint
def get_initial_book(symbol: str) -> Tuple[float,float,float]:
    url = f"{FUTURES_BASE_URL}/ticker/bookTicker"
    r = request_with_retry('GET', url, params={"symbol": symbol})
    d = r.json()
    bid, ask = float(d["bidPrice"]), float(d["askPrice"])
    mid = (bid + ask) / 2.0
    return bid, ask, mid

def sign_request(params: dict) -> str:
    query_string = urlencode(params, True)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{query_string}&signature={signature}"

def _futures_exchange_info(symbol: str):
    url = f"{FUTURES_BASE_URL}/exchangeInfo"
    r = request_with_retry('GET', url, params={"symbol": symbol})
    j = r.json()
    return j["symbols"][0]

# יישור מחיר לבסיס הגריד (דינמי לפי צד)
def align_to_grid(mid: float, step: float, mode: str) -> float:
    if step <= 0: return mid
    dm = Decimal(str(mid))
    ds = Decimal(str(step))
    rounding_mode = ROUND_FLOOR if mode == 'LONG_ONLY' else ROUND_CEILING
    num_steps = (dm / ds)
    aligned = num_steps.to_integral_value(rounding=rounding_mode) * ds
    return float(aligned)

# עיגול/כימות לערכי צעד כמחרוזת מדויקת
def _decimal_places(step: float) -> int:
    ds = Decimal(str(step)).normalize()
    return -ds.as_tuple().exponent if ds.as_tuple().exponent < 0 else 0

def _format_to_step(x: float, step: float, mode=ROUND_DOWN) -> str:
    dx = Decimal(str(x))
    ds = Decimal(str(step))
    q = (dx / ds).to_integral_value(rounding=mode) * ds
    exp = _decimal_places(step)
    return format(q, f".{exp}f")

def _round_to_step_float(x: float, step: float, mode=ROUND_DOWN) -> float:
    return float(_format_to_step(x, step, mode=mode))

# ===== Broker =====
class Broker:
    def __init__(self):
        if DRY_RUN:
            self.is_hedge_mode = False
            # דיפולטים "דומים" ל-SOLUSDT Futures:
            self.step_size = 0.1
            self.tick_size = 0.01
            self.min_qty = 0.1
            self.min_notional = 5.0
            self.qty_prec = _decimal_places(self.step_size)
            self.price_prec = _decimal_places(self.tick_size)
            return

        # קרא פילטרים
        try:
            sym = _futures_exchange_info(SYMBOL)
        except Exception as e:
            print(f"[WARN] exchangeInfo failed, using hardcoded defaults. {e}")
            sym = {"filters":[
                {"filterType":"PRICE_FILTER","tickSize":"0.01"},
                {"filterType":"LOT_SIZE","stepSize":"0.1","minQty":"0.1"},
                {"filterType":"MIN_NOTIONAL","notional":"5.0"}
            ]}
        def get_filter(ft):
            for f in sym.get("filters", []):
                if f.get("filterType") == ft:
                    return f
            return {}
        price_f = get_filter("PRICE_FILTER")
        lot_f = get_filter("LOT_SIZE")
        notional_f= get_filter("MIN_NOTIONAL")

        self.tick_size = float(price_f.get("tickSize", "0.01"))
        self.step_size = float(lot_f.get("stepSize", "0.1"))
        self.min_qty = float(lot_f.get("minQty", "0.1"))
        self.min_notional = float(notional_f.get("notional", "5.0"))

        self.price_prec = _decimal_places(self.tick_size)
        self.qty_prec = _decimal_places(self.step_size)

        # זיהוי מצב פוזיציה בפועל
        self.is_hedge_mode = self.detect_position_mode()

        # ניסיון לאכוף מצב לפי ENV
        if DESIRED_POSITION_MODE in ("HEDGE", "ONEWAY"):
            want_hedge = (DESIRED_POSITION_MODE == "HEDGE")
            if want_hedge != self.is_hedge_mode:
                ok = self.set_position_mode(want_hedge)
                if ok:
                    self.is_hedge_mode = want_hedge
                else:
                    send_telegram_message(
                        f"⚠️ Failed to set position mode to {DESIRED_POSITION_MODE}. "
                        f"Remain: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}*."
                    )

        # אכיפת מצב בטחונות (לא חובה; 400 שכיח אם יש פוזיציה/פקודות פתוחות)
        if MARGIN_MODE != "ISOLATED":
            self.set_margin_mode(MARGIN_MODE)

        send_telegram_message(f"ℹ️ Position mode: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}* | Margin: *{MARGIN_MODE}*")

    # === רענון פילטרים ===
    def refresh_symbol_filters(self):
        try:
            sym = _futures_exchange_info(SYMBOL)
            def get_filter(ft):
                for f in sym.get("filters", []):
                    if f.get("filterType") == ft:
                        return f
                return {}
            price_f = get_filter("PRICE_FILTER")
            lot_f = get_filter("LOT_SIZE")
            notional_f= get_filter("MIN_NOTIONAL")

            self.tick_size = float(price_f.get("tickSize", self.tick_size))
            self.step_size = float(lot_f.get("stepSize", self.step_size))
            self.min_qty = float(lot_f.get("minQty", self.min_qty))
            self.min_notional = float(notional_f.get("notional", self.min_notional))

            self.price_prec = _decimal_places(self.tick_size)
            self.qty_prec = _decimal_places(self.step_size)
        except Exception as e:
            print(f"[WARN] refresh_symbol_filters failed: {e}")

    # ---- Margin Mode ----
    def set_margin_mode(self, margin_type: str) -> bool:
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'symbol': SYMBOL, 'marginType': margin_type}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
            url = f"{FUTURES_BASE_URL}/marginType"
            request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            send_telegram_message(f"✅ *Margin mode set to {margin_type}*")
            return True
        except Exception as e:
            err_text = getattr(e, 'response', None) and getattr(e.response, 'text', str(e))
            print(f"[WARN] set_margin_mode failed: {err_text}")
            send_telegram_message(f"⚠️ Failed to set margin mode to {margin_type}. "
                                    f"סיבות נפוצות: פוזיציות/פקודות פתוחות או שכבר במצב המבוקש.\n{err_text}")
            return False

    # ---- Position Mode ----
    def detect_position_mode(self) -> bool:
        """True = Hedge, False = One-way."""
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_BASE_URL}/positionSide/dual?{signed}"
            r = request_with_retry('GET', url, headers=headers)
            d = r.json()
            return bool(d.get("dualSidePosition", False))
        except Exception as e:
            print(f"[WARN] detect_position_mode failed: {e}. Assuming One-way.")
            return False

    def set_position_mode(self, want_hedge: bool) -> bool:
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'dualSidePosition': 'true' if want_hedge else 'false'}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
            url = f"{FUTURES_BASE_URL}/positionSide/dual"
            request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            return True
        except Exception as e:
            print(f"[WARN] set_position_mode failed: {e}")
            return False

    # ---- Live positions ----
    def _fetch_live_positions(self, symbol: str) -> Dict[str, float]:
        if DRY_RUN:
            wanted_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
            return {wanted_side: sum(p['qty'] for p in positions)}
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000, 'symbol': symbol}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_ACCOUNT_URL}/positionRisk?{signed}"
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
            print(f"[WARN] _fetch_live_positions failed: {e}")
            return {}

    def get_position_qty(self, symbol: str, side: str, live_positions: Dict[str, float]) -> float:
        if not live_positions: return 0.0
        if self.is_hedge_mode:
            return live_positions.get(side, 0.0)
        return live_positions.get('BOTH', 0.0)

    # ---- Orders (עם טיפול -1021/-1111/-4061) ----
    def futures_order(self, params: dict, is_open: bool) -> dict:
        def _do(params):
            params = dict(params)
            params.setdefault('timestamp', ts_ms())
            params.setdefault('recvWindow', 15000)
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
            url = f"{FUTURES_BASE_URL}/order"
            r = request_with_retry('POST', url, headers=headers, data=signed.encode('utf-8'))
            return r

        try:
            return _do(params).json()
        except requests.exceptions.HTTPError as e:
            txt = (e.response.text or "")

            if '"code":-1021' in txt or "-1021" in txt:
                print("[INFO] -1021: syncing server time and retrying once...")
                sync_server_time()
                try:
                    p2 = dict(params)
                    p2['timestamp'] = ts_ms()
                    p2['recvWindow'] = 15000
                    return _do(p2).json()
                except Exception as ee:
                    print(f"[RETRY -1021 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            if '"code":-1111' in txt or "-1111" in txt:
                print("[INFO] -1111: refreshing filters + reclamp qty/price and retrying once...")
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
                    print(f"[RETRY -1111 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            if '"code":-4061' in txt or "-4061" in txt:
                print("[INFO] -4061: re-detecting position mode and retrying once...")
                try:
                    real_hedge = self.detect_position_mode()
                    self.is_hedge_mode = real_hedge
                    p2 = dict(params)
                    if real_hedge:
                        side_hint = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
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
                    print(f"[RETRY -4061 FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")

            try:
                clean = {k: v for k, v in params.items() if k not in ("signature", "recvWindow", "timestamp")}
                send_telegram_message(f"❌ *ORDER ERROR*\n{txt}\nParams: `{clean}`")
            except Exception:
                pass
            raise

    # דיוק מחיר/כמות (ROUND_DOWN) — לשימוש פנימי
    def clamp_price(self, p: float) -> float:
        return _round_to_step_float(p, self.tick_size, mode=ROUND_DOWN)

    def clamp_qty(self, q: float) -> float:
        q = max(q, self.min_qty)
        return _round_to_step_float(q, self.step_size, mode=ROUND_DOWN)

    # יתרה
    def balance_usdt(self) -> float:
        if DRY_RUN:
            return 999999.0
        try:
            params = {'timestamp': ts_ms(), 'recvWindow': 15000}
            signed = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_ACCOUNT_URL}/balance?{signed}"
            r = request_with_retry('GET', url, headers=headers)
            bal = r.json()
            for b in bal:
                if b.get("asset") == "USDT":
                    return float(b.get("availableBalance", 0.0))
            return 0.0
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return COPY_TRADE_ASSUMED_BALANCE
            return 0.0
        except Exception:
            return 0.0

    # קריאות שוק — שליחת כמות כמחרוזת מכומתת
    def market_buy(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
        side_to_open = 'BUY' if STRATEGY_SIDE == 'LONG_ONLY' else 'SELL'
        position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
        qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
        params = {
            'symbol': SYMBOL,
            'side': side_to_open,
            'type': 'MARKET',
            'quantity': qty_str,
        }
        if self.is_hedge_mode:
            params['positionSide'] = position_side
        return self.futures_order(params, is_open=True)

    def market_sell(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
        side_to_close = 'SELL' if STRATEGY_SIDE == 'LONG_ONLY' else 'BUY'
        position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
        qty_str = _format_to_step(qty, self.step_size, mode=ROUND_DOWN)
        params = {
            'symbol': SYMBOL,
            'side': side_to_close,
            'type': 'MARKET',
            'quantity': qty_str,
        }
        if self.is_hedge_mode:
            params['positionSide'] = position_side
        else:
            params['reduceOnly'] = 'true'
        return self.futures_order(params, is_open=False)

broker: Optional[Broker] = None

# ===== לוגיקת גריד =====
def _ensure_min_notional_and_cap(trade_price: float, qty: float) -> Optional[Tuple[float, float]]:
    """
    מאמת שה-qty עומד ב-MIN_NOTIONAL, ואם לא – מגדיל בצורה בטוחה,
    ובודק מגבלת הוצאה יומית. מחזיר (qty, est_cost) או None אם לא ניתן.
    """
    qty = broker.clamp_qty(qty)
    notional = trade_price * qty

    if broker.min_notional and notional < broker.min_notional:
        required = broker.min_notional + broker.tick_size
        req_qty = required / trade_price
        req_qty = broker.clamp_qty(req_qty)
        est_cost = trade_price * req_qty
        if spent_today + est_cost > MAX_DAILY_USDT:
            return None
        if req_qty <= 0:
            return None
        return req_qty, est_cost

    est_cost = trade_price * qty
    if spent_today + est_cost > MAX_DAILY_USDT:
        return None
    return qty, est_cost

def maybe_enter(bid: float, ask: float):
    global positions, total_buys, spent_today
    if len(positions) >= MAX_LADDERS:
        return

    is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")
    position_side = 'LONG' if is_long_strategy else 'SHORT'

    if is_long_strategy:
        next_level = base_price - GRID_STEP_USD * (len(positions) + 1)
        position_trigger = (ask <= next_level)
        trade_price = ask
    else:
        next_level = base_price + GRID_STEP_USD * (len(positions) + 1)
        position_trigger = (bid >= next_level)
        trade_price = bid

    if position_trigger:
        ensured = _ensure_min_notional_and_cap(trade_price, QTY_PER_LADDER)
        if ensured is None:
            log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask), "MinNotional/DailyCap")
            return

        qty, est_cost = ensured

        if not DRY_RUN and broker.balance_usdt() < est_cost * 1.02:
            log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask),
                      f"No USDT. Assuming balance: ${COPY_TRADE_ASSUMED_BALANCE:.2f}")
            return

        try:
            order = broker.market_buy(qty)
            total_buys += 1
            spent_today += 0 if DRY_RUN else est_cost
            positions.append({"entry": trade_price, "qty": float(qty), "buyId": order.get("orderId", "n/a")})
            sp = spread_bps(bid, ask)

            tg_msg = (
                f"🚀 *GRID OPEN: {STRATEGY_SIDE}*\n"
                f"----------------------------\n"
                f"💰 {SYMBOL} @ {trade_price:.4f}\n"
                f"📐 Qty: {qty:.4f}\n"
                f"🏷️ Order ID: {order.get('orderId', 'n/a')}"
            )
            send_telegram_message(tg_msg)

            print(f"\n[ENTER {STRATEGY_SIDE}] qty={qty} @ ~{trade_price:.4f} | open={len(positions)} | spread={sp:.2f}bps | orderId={order.get('orderId','n/a')}")
            log_trade(f"OPEN_{position_side}", trade_price, float(qty), 0.0, realized_pnl, bid, ask, sp, f"orderId={order.get('orderId','n/a')}")
            save_state()
        except requests.exceptions.HTTPError as e:
            print(f"\n[OPEN HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
            log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
            send_telegram_message(f"❌ *OPEN ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code}\n{e.response.text}")
        except Exception as e:
            traceback.print_exc()
            print(f"\n[OPEN ERROR] {e}")
            log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
            send_telegram_message(f"🔥 *CRITICAL OPEN ERROR ({STRATEGY_SIDE})*\n{e}")

def maybe_exit(bid: float, ask: float):
    global positions, realized_pnl, total_sells

    is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")
    exit_price = bid if is_long_strategy else ask # SHORT יוצא ב-Ask

    live_positions = broker._fetch_live_positions(SYMBOL)

    remaining = []
    for p in positions:
        if is_long_strategy:
            target = p["entry"] + TAKE_PROFIT_USD
            exit_condition = (exit_price >= target)
            side_log = "CLOSE_LONG"
            pos_side = 'LONG'
        else:
            target = p["entry"] - TAKE_PROFIT_USD
            exit_condition = (exit_price <= target)
            side_log = "CLOSE_SHORT"
            pos_side = 'SHORT'

        if exit_condition:
            live_qty = broker.get_position_qty(SYMBOL, pos_side, live_positions)
            if live_qty <= 0:
                remaining.append(p)
                continue

            qty_to_close = broker.clamp_qty(min(p["qty"], live_qty))
            try:
                order = broker.market_sell(qty_to_close)

                if is_long_strategy:
                    pnl = (exit_price - p["entry"]) * float(qty_to_close)
                else:
                    pnl = (p["entry"] - exit_price) * float(qty_to_close)

                fee_open = p["entry"] * qty_to_close * TAKER_FEE
                fee_close = exit_price * qty_to_close * TAKER_FEE
                pnl -= (fee_open + fee_close)

                realized_pnl += pnl
                total_sells += 1
                sp = spread_bps(bid, ask)

                tg_msg = (
                    f"✅ *GRID CLOSE: {STRATEGY_SIDE}*\n"
                    f"-------------------------------\n"
                    f"💸 PnL: *+${pnl:.2f}* (Total: ${realized_pnl:.2f})\n"
                    f"💰 Entry @ {p['entry']:.4f}\n"
                    f"💵 Exit @ {exit_price:.4f}\n"
                    f"💳 Fee: ${(fee_open + fee_close):.4f}"
                )
                send_telegram_message(tg_msg)

                print(f"\n[EXIT {STRATEGY_SIDE}] qty={qty_to_close} @ ~{exit_price:.4f} | entry={p['entry']:.4f} | PnL=+${pnl:.2f} | total=${realized_pnl:.2f} | orderId={order.get('orderId','n/a')}")
                log_trade(side_log, exit_price, float(qty_to_close), pnl, realized_pnl, bid, ask, sp, f"orderId={order.get('orderId','n/a')}")
                save_state()

                remaining_qty = float(p["qty"]) - float(qty_to_close)
                if remaining_qty > 0:
                    p2 = dict(p)
                    p2["qty"] = remaining_qty
                    remaining.append(p2)
            except requests.exceptions.HTTPError as e:
                print(f"\n[CLOSE HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
                log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
                send_telegram_message(f"❌ *CLOSE ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code}\n{e.response.text}")
                remaining.append(p)
            except Exception as e:
                traceback.print_exc()
                print(f"\n[CLOSE ERROR] {e}")
                log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
                send_telegram_message(f"🔥 *CRITICAL CLOSE ERROR ({STRATEGY_SIDE})*\n{e}")
                remaining.append(p)
        else:
            remaining.append(p)

    positions[:] = remaining

# ===== Processor =====
def processor(stop_evt: threading.Event):
    global base_price
    last_status = 0.0
    while not stop_evt.is_set():
        curr = datetime.datetime.now().strftime("%Y-%m-%d")
        global spent_date, spent_today
        if curr != spent_date:
            print(f"\n[INFO] Daily spent reset ({spent_date} -> {curr}).")
            spent_today = 0.0
            spent_date = curr
            save_state()

        try:
            bid, ask, mid = msg_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        sp = spread_bps(bid, ask)
        if sp > MAX_SPREAD_BPS:
            if time.time() - last_status > INTERVAL_STATUS_SEC:
                print(f"\rSpread {sp:.2f}bps too wide, waiting... ", end="", flush=True)
                last_status = time.time()
            continue

        is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")

        if is_long_strategy and mid < base_price:
            maybe_enter(bid, ask)
        elif not is_long_strategy and mid > base_price:
            maybe_enter(bid, ask)

        if positions:
            maybe_exit(bid, ask)

        # עדכון base_price רק כשאין פוזיציות
        if not positions and abs(mid - base_price) >= GRID_STEP_USD:
            base_price = align_to_grid(mid, GRID_STEP_USD, STRATEGY_SIDE)
            save_state()

        now = time.time()
        if now - last_status > INTERVAL_STATUS_SEC:
            print(
                f"\rMid={mid:.4f} | Bid={bid:.4f} Ask={ask:.4f} | Spread={sp:.2f}bps | Base={base_price:.0f} | "
                f"Open={len(positions)} | Buys={total_buys} Sells={total_sells} | Realized=${realized_pnl:.2f} | "
                f"SpentToday=${spent_today:.2f} ({STRATEGY_SIDE})",
                end="", flush=True
            )
            last_status = now

# ===== WebSocket =====
last_ws_tick_time = 0.0

class WSClient:
    def __init__(self, url: str):
        self.url = url
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.stop_evt = threading.Event()
        self.reconnect_delay = RECONNECT_MIN

    def on_open(self, ws):
        print("\n[WS] Connected.")
        self.reconnect_delay = RECONNECT_MIN

    def on_message(self, ws, msg):
        try:
            d = json.loads(msg)
            bid, ask = float(d["b"]), float(d["a"])
            mid = (bid + ask) / 2.0
            msg_queue.put_nowait((bid, ask, mid))
            # חותמת זמן טיק
            global last_ws_tick_time
            last_ws_tick_time = time.time()
        except Exception:
            pass

    def on_error(self, ws, err):
        print(f"\n[WS] Error: {err}")

    def on_close(self, ws, code, msg):
        print(f"\n[WS] Closed: {code} {msg}")

    def run_forever(self):
        while not self.stop_evt.is_set():
            self.ws = websocket.WebSocketApp(
                self.url, on_open=self.on_open, on_message=self.on_message,
                on_error=self.on_error, on_close=self.on_close
            )
            self.ws.run_forever(ping_interval=PING_INTERVAL, ping_timeout=PING_TIMEOUT)
            if self.stop_evt.is_set(): break
            delay = min(self.reconnect_delay, RECONNECT_MAX)
            print(f"[WS] Reconnecting in {delay:.1f}s...")
            time.sleep(delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, RECONNECT_MAX)

    def start(self):
        self.thread = threading.Thread(target=self.run_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        if self.thread:
            self.thread.join(timeout=3)

# ===== Price Refresher (REST Poller) =====
class PriceRefresher:
    """
    פולר מחירים בטוח: מריץ בקשת REST כל PRICE_REFRESH_SEC שניות,
    ודוחף לתור את (bid, ask, mid). אם ה-WS שותק יותר מ-STALE_WS_SEC,
    זה משמש כגיבוי.
    """
    def __init__(self, symbol: str, interval_sec: float, stop_evt: threading.Event):
        self.symbol = symbol
        self.interval = max(0.2, float(interval_sec))
        self.stop_evt = stop_evt
        self.thread: Optional[threading.Thread] = None
        self.last_rest_call = 0.0

    def _loop(self):
        global last_ws_tick_time
        while not self.stop_evt.is_set():
            time_since_last_ws = time.time() - last_ws_tick_time
            
            # תמיד נדחוף מחיר עדכני ברענון ה-REST כדי לכסות את פערי ה-WS
            should_refresh = True
            
            # אם ה-WS פעיל, אנחנו יכולים להאט את ה-REST Poller
            if last_ws_tick_time > 0 and time_since_last_ws < STALE_WS_SEC:
                # מדלג על קריאות REST אם לא עבר מספיק זמן
                if time.time() - self.last_rest_call < self.interval:
                    time.sleep(0.1)
                    continue

            # אם ה-WS דומם, לא נדלג.

            try:
                bid, ask, mid = get_initial_book(self.symbol)
                self.last_rest_call = time.time()
                
                try:
                    msg_queue.put_nowait((bid, ask, mid))
                except queue.Full:
                    pass

                if last_ws_tick_time > 0 and time_since_last_ws > STALE_WS_SEC:
                    print(f"\n[WATCHDOG] WS silent for {time_since_last_ws:.1f}s; REST is feeding prices...", flush=True)
            except Exception as e:
                print(f"\n[REFRESHER] REST price fetch failed: {e}", flush=True)

            # המתנה למחזור הבא
            time.sleep(max(0.1, self.interval))


    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        try:
            if self.thread:
                self.thread.join(timeout=2.5)
        except Exception:
            pass

# ===== main + Graceful Shutdown =====
stop_evt = threading.Event()
ws_client: Optional[WSClient] = None
proc_thread: Optional[threading.Thread] = None
price_refresher: Optional[PriceRefresher] = None

def _graceful_exit(signum, frame):
    print(f"\n[Signal {signum}] Graceful shutdown...")
    try:
        save_state()
    except Exception:
        pass
    try:
        if ws_client:
            ws_client.stop()
    except Exception:
        pass
    try:
        stop_evt.set()
        # עצירת הפולר (תלוי ב-stop_evt אבל נסגור יפה)
        try:
            if 'price_refresher' in globals() and price_refresher:
                price_refresher.stop()
        except Exception:
            pass
        if proc_thread:
            proc_thread.join(timeout=3)
    except Exception:
        pass
    print("Bye!")
    os._exit(0)

signal.signal(signal.SIGINT, _graceful_exit)
signal.signal(signal.SIGTERM, _graceful_exit)

def main():
    global base_price, broker, ws_client, proc_thread, price_refresher

    print(f"Starting SOL bot on {SYMBOL} | Mode={'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')}")
    sync_server_time()

    try:
        broker = Broker()
    except Exception as e:
        print(f"[FATAL] Broker initialization failed: {e}")
        traceback.print_exc()
        return

    print("Broker ready.")

    state_loaded = load_state()

    if not state_loaded:
        global spent_date
        spent_date = datetime.datetime.now().strftime("%Y-%m-%d")
        try:
            bid, ask, mid = get_initial_book(SYMBOL)
        except Exception:
            mid = 200.0
            bid, ask = mid - 0.01, mid + 0.01
        base_price = align_to_grid(mid, GRID_STEP_USD, STRATEGY_SIDE)

    print(f"Base price (rounded): {base_price:.0f}")
    print(f"[STRATEGY] Current strategy: {STRATEGY_SIDE}")

    init_csv()

    proc_thread = threading.Thread(target=processor, args=(stop_evt,), daemon=True)
    proc_thread.start()

    ws_client = WSClient(WS_URL)
    ws_client.start()

    # הפעלת פולר המחירים (רפרוש רציף)
    price_refresher = PriceRefresher(SYMBOL, PRICE_REFRESH_SEC, stop_evt)
    price_refresher.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _graceful_exit(2, None)

if __name__ == "__main__":
    main()