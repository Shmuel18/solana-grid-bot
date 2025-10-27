# bot.py — LIVE/Paper trading via Binance Connector + WebSocket prices
# Grid $1, TP $1, 1 SOL לכל מדרגה, Bid/Ask אמיתי, Spread guard, CSV, DRY_RUN, Testnet.
# דרישות: pip install -r requirements.txt

import os, time, json, threading, queue, csv, datetime, requests, math, uuid
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv
import websocket
from binance.spot import Spot as BinanceSpot

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

PING_INTERVAL = 20.0
RECONNECT_MIN, RECONNECT_MAX = 1.0, 30.0

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("BINANCE_USE_TESTNET", "no").lower() == "yes"
DRY_RUN = os.getenv("DRY_RUN", "yes").lower() == "yes"

MAX_DAILY_USDT = float(os.getenv("MAX_DAILY_USDT", "200"))  # תקרת קניות יומית

# ===== מצב =====
base_price = 0.0  # תמיד מעוגל לשלם
positions: List[Dict] = []  # [{entry: float, qty: float, buyId: str}]
realized_pnl = 0.0
total_buys = 0
total_sells = 0
spent_today = 0.0

msg_queue: "queue.Queue[Tuple[float,float,float]]" = queue.Queue(maxsize=1000)

# ===== CSV =====
def init_csv():
    new = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time","side","price","qty","pnl","total_pnl","bid","ask","spread_bps","note"])

def log_trade(side: str, price: float, qty: float, pnl: float, total: float,
              bid: float, ask: float, spread_bps: float, note: str = ""):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            side, f"{price:.4f}", f"{qty:.6f}", f"{pnl:.4f}", f"{total:.4f}",
            f"{bid:.4f}", f"{ask:.4f}", f"{spread_bps:.3f}", note
        ])

# ===== עזר =====
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

# ===== ברוקר (Binance Connector) =====
class Broker:
    def __init__(self):
        base_url = "https://testnet.binance.vision" if USE_TESTNET else "https://api.binance.com"

        # נבנה לקוח רק אם המפתחות ascii ולא ריקים; אחרת—לקוח ללא מפתחות (מספיק לרוב הקריאות הציבוריות)
        kwargs = {"base_url": base_url}
        if API_KEY and API_SECRET and is_ascii(API_KEY) and is_ascii(API_SECRET):
            kwargs.update({"api_key": API_KEY, "api_secret": API_SECRET})
        self.client = BinanceSpot(**kwargs)

        # נשלוף info מצומצם רק לסימבול שלנו
        info = self.client.exchange_info(symbol=SYMBOL)
        sym = info["symbols"][0]

        def get_filter(ftype: str):
            for f in sym.get("filters", []):
                if f.get("filterType") == ftype:
                    return f
            return None

        price_f = get_filter("PRICE_FILTER") or {}
        lot_f   = get_filter("LOT_SIZE") or {}
        # יש בורסות/גרסאות בהן MIN_NOTIONAL חסר/מוחלף בשם NOTIONAL
        min_notional_f = get_filter("MIN_NOTIONAL") or get_filter("NOTIONAL") or {}

        tick_size = float(price_f.get("tickSize", "0.01"))
        step_size = float(lot_f.get("stepSize",  "0.001"))

        self.price_prec = max(0, -int(round(math.log10(tick_size)))) if tick_size > 0 else 2
        self.qty_prec   = max(0, -int(round(math.log10(step_size)))) if step_size > 0 else 3

        self.min_qty      = float(lot_f.get("minQty", "0"))
        self.min_notional = float(min_notional_f.get("minNotional", "0"))

    def clamp_price(self, p: float) -> float:
        return float(f"{p:.{self.price_prec}f}")

    def clamp_qty(self, q: float) -> float:
        q = max(q, self.min_qty)
        return float(f"{q:.{self.qty_prec}f}")

    def balance_usdt(self) -> float:
        try:
            bal = self.client.account()
            for b in bal.get("balances", []):
                if b.get("asset") == "USDT":
                    return float(b.get("free", 0.0))
        except Exception:
            pass
        return 0.0

    def market_buy(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
        return self.client.new_order(symbol=SYMBOL, side="BUY", type="MARKET", quantity=qty)

    def market_sell(self, qty: float) -> dict:
        if DRY_RUN:
            return {"orderId": f"dry-{uuid.uuid4()}", "executedQty": str(qty)}
        return self.client.new_order(symbol=SYMBOL, side="SELL", type="MARKET", quantity=qty)

broker: Optional[Broker] = None

# ===== לוגיקה =====
def maybe_enter(bid: float, ask: float):
    global positions, total_buys, spent_today
    if len(positions) >= MAX_LADDERS:
        return
    next_level = base_price - GRID_STEP_USD * (len(positions) + 1)
    buy_price = ask
    if buy_price <= next_level:
        est_cost = buy_price * QTY_PER_LADDER
        if spent_today + est_cost > MAX_DAILY_USDT:
            log_trade("SKIP_BUY", buy_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask), "Daily cap")
            return
        if not DRY_RUN and broker.balance_usdt() < est_cost * 1.02:
            log_trade("SKIP_BUY", buy_price, 0, 0, realized_pnl, bid, ask, spread_bps(bid, ask), "No USDT")
            return
        qty = broker.clamp_qty(QTY_PER_LADDER)
        try:
            order = broker.market_buy(qty)
            total_buys += 1
            spent_today += 0 if DRY_RUN else est_cost
            positions.append({"entry": buy_price, "qty": float(qty), "buyId": order["orderId"]})
            sp = spread_bps(bid, ask)
            print(f"\n[ENTER {'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')}] qty={qty} @ ~{buy_price:.4f} | open={len(positions)} | spread={sp:.2f}bps | orderId={order['orderId']}")
            log_trade("BUY", buy_price, float(qty), 0.0, realized_pnl, bid, ask, sp, f"orderId={order['orderId']}")
        except Exception as e:
            print(f"\n[BUY ERROR] {e}")
            log_trade("BUY_ERROR", buy_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))

def maybe_exit(bid: float, ask: float):
    global positions, realized_pnl, total_sells
    sell_price = bid
    remaining = []
    for p in positions:
        target = p["entry"] + TAKE_PROFIT_USD
        if sell_price >= target:
            qty = broker.clamp_qty(p["qty"])
            try:
                order = broker.market_sell(qty)
                pnl = (sell_price - p["entry"]) * float(qty)
                realized_pnl += pnl
                total_sells += 1
                sp = spread_bps(bid, ask)
                print(f"\n[EXIT {'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')}] qty={qty} @ ~{sell_price:.4f} | entry={p['entry']:.4f} | PnL=+${pnl:.2f} | total=${realized_pnl:.2f} | orderId={order['orderId']}")
                log_trade("SELL", sell_price, float(qty), pnl, realized_pnl, bid, ask, sp, f"orderId={order['orderId']}")
            except Exception as e:
                print(f"\n[SELL ERROR] {e}")
                log_trade("SELL_ERROR", sell_price, float(qty), 0.0, realized_pnl, bid, ask, spread_bps(bid, ask), str(e))
                remaining.append(p)
        else:
            remaining.append(p)
    positions[:] = remaining

# ===== עיבוד הודעות =====
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

        if mid < base_price:
            maybe_enter(bid, ask)
        if positions:
            maybe_exit(bid, ask)

        # עדכון בסיס (כשהסולם ריק) — למספר עגול
        if not positions and abs(mid - base_price) >= GRID_STEP_USD:
            base_price = round(mid)

        now = time.time()
        if now - last_status > INTERVAL_STATUS_SEC:
            print(
                f"\rMid={mid:.4f} | Bid={bid:.4f} Ask={ask:.4f} | Spread={sp:.2f}bps | Base={base_price:.0f} | "
                f"Open={len(positions)} | Buys={total_buys} Sells={total_sells} | Realized=${realized_pnl:.2f} | "
                f"SpentToday=${spent_today:.2f} ({'DRY' if DRY_RUN else ('TESTNET' if USE_TESTNET else 'LIVE')})",
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

    bid, ask, mid = get_initial_book(SYMBOL)
    base_price = round(mid)
    print(f"Base price (rounded): {base_price:.0f}")

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
        client.stop()
        stop_evt.set()
        proc_thread.join(timeout=3)
        print("Bye!")

if __name__ == "__main__":
    main()
