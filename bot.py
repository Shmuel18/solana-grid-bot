# bot.py — LIVE/Paper trading via Binance Futures Connector
# תיקונים: זיהוי מצב פוזיציה (Hedge/One-Way) + Retry חכם ל-4061 + בדיקת כמות חיה לפני סגירה
# ותיקון -1106: ב-Hedge אין לשלוח reduceOnly, ב-One-way כן.

import os, time, json, threading, queue, csv, datetime, requests, math, uuid
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv
import websocket
from binance.spot import Spot as BinanceSpot
import hmac, hashlib
from urllib.parse import urlencode
import traceback

load_dotenv()

# ===== קונפיג =====
SYMBOL = os.getenv("SYMBOL", "SOLUSDT").upper()
STREAM_SYMBOL = SYMBOL.lower()
WS_URL = f"wss://stream.binance.com:9443/ws/{STREAM_SYMBOL}@bookTicker"

GRID_STEP_USD = float(os.getenv("GRID_STEP_USD", "1.0"))
TAKE_PROFIT_USD = float(os.getenv("TAKE_PROFIT_USD", "1.0"))
MAX_LADDERS = int(os.getenv("MAX_LADDERS", "20"))
QTY_PER_LADDER = float(os.getenv("QTY_PER_LADDER", "1.0"))
MAX_SPREAD_BPS = float(os.getenv("MAX_SPREAD_BPS", "8"))
INTERVAL_STATUS_SEC = float(os.getenv("INTERVAL_STATUS_SEC", "1.5"))
CSV_FILE = os.getenv("CSV_FILE", "trades.csv")
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

PING_INTERVAL = 20.0
RECONNECT_MIN, RECONNECT_MAX = 1.0, 30.0

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("BINANCE_USE_TESTNET", "no").lower() == "yes"
DRY_RUN = os.getenv("DRY_RUN", "yes").lower() == "yes"
COPY_TRADE_ASSUMED_BALANCE = float(os.getenv("COPY_TRADE_ASSUMED_BALANCE", "500.0"))

MAX_DAILY_USDT = float(os.getenv("MAX_DAILY_USDT", "200"))

# === טלגרם ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === אסטרטגיה וזיהוי מצב ===
STRATEGY_SIDE = os.getenv("STRATEGY_SIDE", "LONG_ONLY").upper()  # LONG_ONLY or SHORT_ONLY
if STRATEGY_SIDE not in ["LONG_ONLY", "SHORT_ONLY"]:
    print(f"[FATAL] Invalid STRATEGY_SIDE: {STRATEGY_SIDE}. Defaulting to LONG_ONLY.")
    STRATEGY_SIDE = "LONG_ONLY"

DESIRED_POSITION_MODE = os.getenv("DESIRED_POSITION_MODE", "").upper()  # "", "HEDGE", "ONEWAY"

# Futures API Endpoints
FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1"
FUTURES_ACCOUNT_URL = "https://fapi.binance.com/fapi/v2"  # balance, positionRisk

# ===== מצב (Status) =====
base_price = 0.0
positions: List[Dict] = []
realized_pnl = 0.0
total_buys = 0
total_sells = 0
spent_today = 0.0

msg_queue: "queue.Queue[Tuple[float,float,float]]" = queue.Queue(maxsize=1000)

# ===== טלגרם =====
def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"\n[TELEGRAM ERROR] Failed to send message: {e}")

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
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def load_state():
    global base_price, positions, realized_pnl, total_buys, total_sells, spent_today
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
                print(f"\n[STATE] Loaded state from {STATE_FILE}. Open positions: {len(positions)}")
                return True
            except Exception as e:
                print(f"\n[WARNING] Failed to load state from {STATE_FILE}: {e}. Starting fresh.")
                return False
    return False

# ===== Helpers =====
def is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except Exception:
        return False

def spread_bps(bid: float, ask: float) -> float:
    if ask <= 0: return 9999.0
    return (ask - bid) / ask * 10_000

def get_initial_book(symbol: str) -> Tuple[float,float,float]:
    url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
    d = requests.get(url, timeout=5).json()
    bid, ask = float(d["bidPrice"]), float(d["askPrice"])
    mid = (bid + ask) / 2.0
    return bid, ask, mid

def sign_request(params: dict) -> str:
    query_string = urlencode(params, True)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{query_string}&signature={signature}"

# ===== Broker =====
class Broker:
    def __init__(self):
        base_url = "https://testnet.binance.vision" if USE_TESTNET else "https://api.binance.com"
        kwargs = {"base_url": base_url}
        if API_KEY and API_SECRET and is_ascii(API_KEY) and is_ascii(API_SECRET):
            kwargs.update({"api_key": API_KEY, "api_secret": API_SECRET})
        self.client = BinanceSpot(**kwargs)

        # מצב פוזיציה בפועל
        self.is_hedge_mode = self.detect_position_mode()

        # נסיון לאכוף מצב לפי ENV (אופציונלי)
        if DESIRED_POSITION_MODE in ("HEDGE", "ONEWAY"):
            want_hedge = (DESIRED_POSITION_MODE == "HEDGE")
            if want_hedge != self.is_hedge_mode:
                ok = self.set_position_mode(want_hedge)
                if ok:
                    self.is_hedge_mode = want_hedge
                else:
                    send_telegram_message(
                        f"⚠️ לא הצלחתי לשנות מצב פוזיציה ל-{DESIRED_POSITION_MODE}. "
                        f"נשארים על *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}*."
                    )

        # דיווח מצב לטלגרם
        send_telegram_message(f"ℹ️ Position mode: *{'HEDGE' if self.is_hedge_mode else 'ONE-WAY'}*")

        # פרמטרי סימבול (דיוק/מינימום)
        try:
            info = self.client.exchange_info(symbol=SYMBOL)
            sym = info["symbols"][0]
        except Exception:
            sym = {"filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                               {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"}]}

        def get_filter(ftype: str):
            for f in sym.get("filters", []):
                if f.get("filterType") == ftype:
                    return f
            return None

        price_f = get_filter("PRICE_FILTER") or {}
        lot_f   = get_filter("LOT_SIZE") or {}

        tick_size = float(price_f.get("tickSize", "0.01"))
        step_size = float(lot_f.get("stepSize",  "0.001"))

        self.price_prec = max(0, -int(round(math.log10(tick_size)))) if tick_size > 0 else 2
        self.qty_prec   = max(0, -int(round(math.log10(step_size)))) if step_size > 0 else 3
        self.min_qty    = float(lot_f.get("minQty", "0"))

    # ---- זיהוי/קביעה של מצב פוזיציה ----
    def detect_position_mode(self) -> bool:
        """True = Hedge, False = One-way."""
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp, 'recvWindow': 5000}
            signed_query = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_BASE_URL}/positionSide/dual?{signed_query}"
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            d = r.json()
            return bool(d.get("dualSidePosition", False))
        except Exception as e:
            print(f"[WARN] detect_position_mode failed: {e}. Assuming One-way.")
            return False

    def set_position_mode(self, want_hedge: bool) -> bool:
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp, 'recvWindow': 5000, 'dualSidePosition': 'true' if want_hedge else 'false'}
            signed_query = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
            url = f"{FUTURES_BASE_URL}/positionSide/dual"
            r = requests.post(url, headers=headers, data=signed_query.encode('utf-8'), timeout=5)
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"[WARN] set_position_mode failed: {e}")
            return False

    # ---- שאיבת כמות חיה ----
    def get_position_qty(self, symbol: str, side: str) -> float:
        """
        side: 'LONG' or 'SHORT'
        מחזיר גודל פוזיציה בצד המבוקש (abs), 0 אם אין.
        """
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp, 'recvWindow': 5000}
            signed_query = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_ACCOUNT_URL}/positionRisk?{signed_query}"
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            arr = r.json()
            qty = 0.0
            want = 'BOTH'
            if self.is_hedge_mode:
                want = side  # 'LONG' or 'SHORT'
            for p in arr:
                if p.get('symbol') != symbol:
                    continue
                ps = p.get('positionSide', 'BOTH')
                if ps != want:
                    continue
                size = float(p.get('positionAmt', 0.0) or 0.0)
                qty = max(qty, abs(size))
            return max(qty, 0.0)
        except Exception as e:
            print(f"[WARN] get_position_qty failed: {e}")
            return 0.0

    # ---- שליחת הוראת FUTURES עם רטריי חכם ----
    def futures_order(self, params: dict) -> dict:
        signed_query = sign_request(params)
        headers = {'X-MBX-APIKEY': API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
        url = f"{FUTURES_BASE_URL}/order"

        try:
            resp = requests.post(url, headers=headers, data=signed_query.encode('utf-8'), timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            txt = (e.response.text or "")
            if '"code":-4061' in txt or "-4061" in txt:
                print("[INFO] -4061: re-detecting position mode and retrying once...")
                try:
                    real_hedge = self.detect_position_mode()
                    self.is_hedge_mode = real_hedge
                    p2 = params.copy()
                    if real_hedge:
                        side_hint = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'
                        p2['positionSide'] = side_hint
                        p2.pop('reduceOnly', None)  # ליתר בטחון
                    else:
                        p2.pop('positionSide', None)
                        p2['reduceOnly'] = 'true'
                    signed2 = sign_request(p2)
                    resp2 = requests.post(url, headers=headers, data=signed2.encode('utf-8'), timeout=5)
                    resp2.raise_for_status()
                    send_telegram_message(
                        f"✅ *SUCCESS AFTER RETRY* — Position mode confirmed: "
                        f"*{'HEDGE' if real_hedge else 'ONE-WAY'}*"
                    )
                    return resp2.json()
                except Exception as ee:
                    print(f"[RETRY FAILED] {getattr(ee, 'response', None) and getattr(ee.response, 'text', '')}")
            # שלח לטלגרם פירוט מינימלי בלי סיגנצ'ר
            try:
                clean_params = {k: v for k, v in params.items() if k not in ("signature",)}
                send_telegram_message(f"❌ *ORDER ERROR*\n{txt}\nParams: `{clean_params}`")
            except Exception:
                pass
            raise

    def clamp_price(self, p: float) -> float:
        return float(f"{p:.{self.price_prec}f}")

    def clamp_qty(self, q: float) -> float:
        q = max(q, self.min_qty)
        return float(f"{q:.{self.qty_prec}f}")

    def balance_usdt(self) -> float:
        if DRY_RUN:
            return 999999.0
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp, 'recvWindow': 5000}
            signed_query = sign_request(params)
            headers = {'X-MBX-APIKEY': API_KEY}
            url = f"{FUTURES_ACCOUNT_URL}/balance?{signed_query}"
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            bal = response.json()
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

    def market_buy(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}

        side_to_open = 'BUY' if STRATEGY_SIDE == 'LONG_ONLY' else 'SELL'
        position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'

        timestamp = int(time.time() * 1000)
        params = {
            'symbol': SYMBOL,
            'side': side_to_open,
            'type': 'MARKET',
            'quantity': qty,
            'timestamp': timestamp,
            'recvWindow': 5000,
        }
        if self.is_hedge_mode:
            params['positionSide'] = position_side

        return self.futures_order(params)

    def market_sell(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}

        side_to_close = 'SELL' if STRATEGY_SIDE == 'LONG_ONLY' else 'BUY'
        position_side = 'LONG' if STRATEGY_SIDE == 'LONG_ONLY' else 'SHORT'

        timestamp = int(time.time() * 1000)
        params = {
            'symbol': SYMBOL,
            'side': side_to_close,
            'type': 'MARKET',
            'quantity': qty,
            'timestamp': timestamp,
            'recvWindow': 5000,
            # שים לב: לא שמים reduceOnly כברירת מחדל
        }
        if self.is_hedge_mode:
            # ב-Hedge: סוגרים לונג/שורט ע"י side הפוך + positionSide מתאים — בלי reduceOnly
            params['positionSide'] = position_side
        else:
            # ב-One-way: נשתמש ב-reduceOnly כדי לא לפתוח כיוון הפוך בטעות
            params['reduceOnly'] = 'true'

        return self.futures_order(params)

broker: Optional[Broker] = None

# ===== לוגיקת גריד =====
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
        est_cost = trade_price * QTY_PER_LADDER
        if spent_today + est_cost > MAX_DAILY_USDT:
            log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask), "Daily cap")
            return

        if not DRY_RUN and broker.balance_usdt() < est_cost * 1.02:
            log_trade("SKIP_BUY", trade_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask),
                      f"No USDT. Assuming balance: ${COPY_TRADE_ASSUMED_BALANCE:.2f}")
            return

        qty = broker.clamp_qty(QTY_PER_LADDER)
        try:
            order = broker.market_buy(qty)
            total_buys += 1
            spent_today += 0 if DRY_RUN else est_cost
            positions.append({"entry": trade_price, "qty": float(qty), "buyId": order["orderId"]})
            sp = spread_bps(bid, ask)

            tg_msg = (
                f"🚀 *GRID OPEN: {STRATEGY_SIDE}*\n"
                f"----------------------------\n"
                f"💰 {SYMBOL} @ {trade_price:.4f}\n"
                f"📐 Qty: {qty:.4f}\n"
                f"🏷️ Order ID: {order['orderId']}"
            )
            send_telegram_message(tg_msg)

            print(f"\n[ENTER {STRATEGY_SIDE}] qty={qty} @ ~{trade_price:.4f} | open={len(positions)} | spread={sp:.2f}bps | orderId={order['orderId']}")
            log_trade(f"OPEN_{position_side}", trade_price, float(qty), 0.0, realized_pnl, bid, ask, sp, f"orderId={order['orderId']}")
            save_state()
        except requests.exceptions.HTTPError as e:
            error_msg = f"❌ *OPEN ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code} | Message: {e.response.text}"
            send_telegram_message(error_msg)
            print(f"\n[OPEN HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
            log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
        except Exception as e:
            error_msg = f"🔥 *CRITICAL ERROR ({STRATEGY_SIDE})*\nDetails: {e}"
            send_telegram_message(error_msg)
            traceback.print_exc()
            print(f"\n[OPEN ERROR] {e}")
            log_trade("OPEN_ERROR", trade_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))

def maybe_exit(bid: float, ask: float):
    global positions, realized_pnl, total_sells

    is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")
    exit_price = bid

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
            # כמות חיה בפועל בצד המתאים
            live_qty = broker.get_position_qty(SYMBOL, pos_side)
            if live_qty <= 0:
                # אין פוזיציה חיה — לא סוגרים את הרשומה הזו עדיין
                remaining.append(p)
                continue

            qty_to_close = broker.clamp_qty(min(p["qty"], live_qty))
            try:
                order = broker.market_sell(qty_to_close)

                if is_long_strategy:
                    pnl = (exit_price - p["entry"]) * float(qty_to_close)
                else:
                    pnl = (p["entry"] - exit_price) * float(qty_to_close)

                realized_pnl += pnl
                total_sells += 1
                sp = spread_bps(bid, ask)

                tg_msg = (
                    f"✅ *GRID CLOSE: {STRATEGY_SIDE}*\n"
                    f"-------------------------------\n"
                    f"💸 PnL: *+${pnl:.2f}* (Total: ${realized_pnl:.2f})\n"
                    f"💰 Entry @ {p['entry']:.4f}\n"
                    f"💵 Exit @ {exit_price:.4f}\n"
                )
                send_telegram_message(tg_msg)

                print(f"\n[EXIT {STRATEGY_SIDE}] qty={qty_to_close} @ ~{exit_price:.4f} | entry={p['entry']:.4f} | PnL=+${pnl:.2f} | total=${realized_pnl:.2f} | orderId={order['orderId']}")
                log_trade(side_log, exit_price, float(qty_to_close), pnl, realized_pnl, bid, ask, sp, f"orderId={order['orderId']}")
                save_state()

                # אם סגרנו חלקית — השאר את היתרה
                remaining_qty = float(p["qty"]) - float(qty_to_close)
                if remaining_qty > 0:
                    p2 = dict(p)
                    p2["qty"] = remaining_qty
                    remaining.append(p2)
            except requests.exceptions.HTTPError as e:
                error_msg = f"❌ *CLOSE ERROR ({STRATEGY_SIDE})*\nStatus: {e.response.status_code}\nMessage: {e.response.text}"
                send_telegram_message(error_msg)
                print(f"\n[CLOSE HTTP ERROR] Status: {e.response.status_code} | Message: {e.response.text}")
                log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), f"HTTP Error: {e.response.text}")
                remaining.append(p)
            except Exception as e:
                error_msg = f"🔥 *CRITICAL ERROR ({STRATEGY_SIDE})*\nDetails: {e}"
                send_telegram_message(error_msg)
                print(f"\n[CLOSE ERROR] {e}")
                log_trade("CLOSE_ERROR", exit_price, float(qty_to_close), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
                remaining.append(p)
        else:
            remaining.append(p)
    positions[:] = remaining

# ===== Processor =====
def processor(stop_evt: threading.Event):
    global base_price
    last_status = 0.0
    while not stop_evt.is_set():
        try:
            bid, ask, mid = msg_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        sp = spread_bps(bid, ask)
        if sp > MAX_SPREAD_BPS:
            if time.time() - last_status > INTERVAL_STATUS_SEC:
                print(f"\rSpread {sp:.2f}bps too wide, waiting...  ", end="", flush=True)
                last_status = time.time()
            continue

        is_long_strategy = (STRATEGY_SIDE == "LONG_ONLY")

        if is_long_strategy and mid < base_price:
            maybe_enter(bid, ask)
        elif not is_long_strategy and mid > base_price:
            maybe_enter(bid, ask)

        if positions:
            maybe_exit(bid, ask)

        if not positions and abs(mid - base_price) >= GRID_STEP_USD:
            base_price = round(mid)
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
        except Exception:
            pass

    def on_error(self, ws, err): print(f"\n[WS] Error: {err}")
    def on_close(self, ws, code, msg): print(f"\n[WS] Closed: {code} {msg}")

    def run_forever(self):
        while not self.stop_evt.is_set():
            self.ws = websocket.WebSocketApp(
                self.url, on_open=self.on_open, on_message=self.on_message,
                on_error=self.on_error, on_close=self.on_close
            )
            self.ws.run_forever(ping_interval=PING_INTERVAL, ping_timeout=10)
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
        try: self.ws.close()
        except Exception: pass
        if self.thread: self.thread.join(timeout=3)

# ===== main =====
def main():
    global base_price, broker
    print(f"Starting SOL bot on {SYMBOL} | Mode={'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')}")
    broker = Broker()
    print("Broker ready.")

    state_loaded = load_state()

    if not state_loaded:
        try:
            bid, ask, mid = get_initial_book(SYMBOL)
        except Exception:
            mid = 200.0
            bid, ask = mid - 0.01, mid + 0.01
        base_price = round(mid)

    print(f"Base price (rounded): {base_price:.0f}")
    print(f"[STRATEGY] Current strategy: {STRATEGY_SIDE}")

    init_csv()

    stop_evt = threading.Event()
    proc_thread = threading.Thread(target=processor, args=(stop_evt,), daemon=True)
    proc_thread.start()

    client = WSClient(WS_URL)
    client.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping...")
        save_state()
        client.stop()
        stop_evt.set()
        proc_thread.join(timeout=3)
        print("Bye!")

if __name__ == "__main__":
    main()
