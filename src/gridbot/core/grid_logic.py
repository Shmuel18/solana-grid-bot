import time
from typing import Dict, Tuple, List, Set, Optional

from gridbot.config.settings import Settings
from gridbot.state.manager import StateManager, BotState, Position
from gridbot.broker.binance_connector import Broker
from gridbot.broker.notifications import send_telegram_message
from gridbot.core.utils import dprint, format_step, align_to_grid

class GridManager:
    def __init__(self, settings: Settings, state_manager: StateManager, broker: Broker):
        self.settings = settings
        self.state_manager = state_manager
        self.broker = broker
        self.state = state_manager.state
        self.price_suppress_until: Dict[float, float] = {}
        self.pending_submissions: Set[float] = set()
        self.pending_since: Dict[float, float] = {}
        self.suspected_filled: Dict[str, float] = {}

    # --- Utility Helpers ---

    def _is_ours(self, o: Dict) -> bool:
        """Checks if an order belongs to this bot session."""
        try:
            cid = str(o.get("clientOrderId") or o.get("client_order_id") or o.get("client_id") or "")
        except Exception:
            return False
        if not cid:
            return False
        return cid.startswith(f"B-{self.broker.session_tag}-") or cid.startswith(f"T-{self.broker.session_tag}-")

    def tp_client_id(self, entry: float, qty: float) -> str:
        """Generates a deterministic client ID for a TP order."""
        return f"T-{self.broker.session_tag}-{int(round(entry * 100))}-{int(round(qty * 1000))}"

    def _allowed_new_buys_now(self) -> Tuple[int, Dict[str, int]]:
        """Calculates the maximum number of new BUY orders allowed based on limits."""
        open_buys = len(self.state.open_buy_price_to_id)
        pos_lots = len(self.state.positions)
        cap_trades = self.settings.MAX_OPEN_TRADES - (pos_lots + open_buys)
        cap_ladders = self.settings.MAX_LADDERS - open_buys
        allowed = max(0, min(cap_trades, cap_ladders))
        meta = {
            "pos_lots": pos_lots,
            "open_buys": open_buys,
            "cap_trades": cap_trades,
            "cap_ladders": cap_ladders,
            "allowed": allowed,
        }
        return allowed, meta

    def _persistent_recent_hot(self, px: float, now_ts: float) -> bool:
        """Checks if a price is in persistent cooldown across restarts."""
        ts = float(self.state.recent_submissions.get(str(px), 0.0))
        if ts <= 0:
            return False
        return (now_ts - ts) < self.settings.DUPLICATE_COOLDOWN_SEC

    # --- Exchange Sync ---

    def sync_open_from_exchange_full(self):
        """Updates local open BUY map and TP blocked entries from exchange orders."""
        tmp_open: Dict[float, str] = dict(self.state.open_buy_price_to_id)
        tmp_tp_blocked: Set[float] = set(p.entry for p in self.state.positions)

        if self.settings.DRY_RUN:
            self.state.tp_blocked_entries = tmp_tp_blocked
            return

        try:
            orders = self.broker.get_open_orders()
        except Exception as e:
            print(f"[WARN] get_open_orders failed: {e} (keeping previous maps)")
            return

        # Clear map and rebuild from live orders to ensure accuracy
        tmp_open.clear()

        for o in orders:
            try:
                side = str(o.get("side", ""))
                status = str(o.get("status", ""))
                if status not in ("NEW", "PARTIALLY_FILLED"):
                    continue
                price = self.broker.clamp_price(float(o.get("price", "0")))
                reduce_only = str(o.get("reduceOnly") or o.get("reduce_only") or o.get("reduce_only_flag") or "").lower() in ("true","1")
                
                if side == "BUY" and not reduce_only:
                    if self._is_ours(o):
                        tmp_open[price] = str(o.get("orderId", ""))
                elif side == "SELL" and reduce_only:
                    entry = self.broker.clamp_price(price - self.settings.TAKE_PROFIT_USD)
                    tmp_tp_blocked.add(entry)
            except Exception:
                continue

        self.state.open_buy_price_to_id = tmp_open
        self.state.tp_blocked_entries = tmp_tp_blocked

    def ensure_tps_for_positions(self):
        """Checks all positions and places missing TP orders."""
        if self.settings.DRY_RUN:
            dprint("[TP-RECOVER] DRY_RUN=True -> skip placing live TPs")
            return

        try:
            live_orders = self.broker.get_open_orders()
        except Exception as e:
            print(f"[TP-RECOVER] get_open_orders failed: {e}")
            live_orders = []

        placed = 0
        for lot in list(self.state.positions):
            if lot.qty <= 0:
                continue
            
            entry = lot.entry
            qty = lot.qty
            tp_price = self.broker.clamp_price(entry + self.settings.TAKE_PROFIT_USD)

            if self._orders_has_live_tp(live_orders, tp_price, qty):
                dprint(f"[TP-RECOVER] live TP exists @ {tp_price} qty={qty}")
                continue
            
            try:
                cid = self.tp_client_id(entry, qty)
                od = self.broker.limit_tp_reduce(entry, qty, client_order_id=cid)
                tp_id = str(od.get("orderId", "n/a"))
                lot.tp_price = tp_price
                lot.tp_id = tp_id
                self.state.tp_blocked_entries.add(self.broker.clamp_price(entry))
                placed += 1
                self.state_manager.log_trade("LIMIT_TP_RECOVER_OPEN", tp_price, qty, 0.0, f"tpId={tp_id}")
                send_telegram_message(self.settings, f"✅ TP RECOVER {self.settings.SYMBOL} @ {tp_price:.4f} | Qty {qty:.4f}")
            except Exception as e:
                dprint(f"[TP-RECOVER] error placing TP for entry {entry}: {e}")
                self.state_manager.log_trade("LIMIT_TP_RECOVER_ERROR", tp_price, qty, 0.0, str(e))

        if placed:
            self.state_manager.save_state()
        print(f"[TP-RECOVER] total newly opened: {placed}")

    def _orders_has_live_tp(self, orders: List[Dict], tp_price: float, qty: float) -> bool:
        tp_price = self.broker.clamp_price(tp_price)
        qty = self.broker.clamp_qty(qty)
        for o in orders:
            try:
                side = str(o.get("side", ""))
                status = str(o.get("status", ""))
                reduce_only = str(o.get("reduceOnly") or o.get("reduce_only") or o.get("reduce_only_flag") or "").lower() in ("true","1")
                op = self.broker.clamp_price(float(o.get("price", 0.0)))
                oq = self.broker.clamp_qty(float(o.get("origQty", 0.0)))
            except Exception:
                continue
            if side == "SELL" and reduce_only and status in ("NEW", "PARTIALLY_FILLED"):
                # Compare prices and quantities within tolerance
                if abs(op - tp_price) < max(self.broker.tick_size, 1e-9) and abs(oq - qty) < max(self.broker.step_size, 1e-9):
                    return True
        return False

    # --- Grid Management ---

    def build_grid_candidates(self, base: float) -> List[float]:
        """Generates potential BUY prices below the base price, excluding TP-blocked entries."""
        levels: List[float] = []
        i = 1
        seen = set()
        
        # Use the derived state for blocked entries
        blocked_prices = self.state.tp_blocked_entries

        while True:
            px = self.broker.clamp_price(base - self.settings.GRID_STEP_USD * i)
            if px not in seen:
                levels.append(px)
                seen.add(px)
            
            # Check if we have enough usable levels (not blocked)
            usable = [p for p in levels if (p not in blocked_prices)]
            if len(usable) >= self.settings.MAX_LADDERS:
                # Return all generated levels, sorted descending
                return sorted(set(levels), reverse=True)
            
            i += 1
            if i > 20000: # Safety break
                return sorted(set(levels), reverse=True)

    def place_missing_buys(self, levels: List[float], ignore_recent: bool = False):
        """Places new limit BUY orders to fill the grid depth."""
        if self.state.HALT_PLACEMENT:
            dprint("[SKIP] HALT_PLACEMENT=True — blocking new orders")
            return

        allowed, meta = self._allowed_new_buys_now()
        dprint(f"[CAP] posLots={meta['pos_lots']} openBuys={meta['open_buys']} "
               f"capTrades={meta['cap_trades']} capLadders={meta['cap_ladders']} -> allowed={allowed}")

        if allowed <= 0:
            dprint("[SKIP] No capacity to open new BUYs (allowed<=0)")
            return

        now_ts = time.time()
        
        # Purge old in-memory cooldowns
        for k, t in list(self.price_suppress_until.items()):
            if now_ts >= t:
                self.price_suppress_until.pop(k, None)
        for px_pending, ts in list(self.pending_since.items()):
            if now_ts - ts > self.settings.PENDING_LOCK_MAX_SEC:
                self.pending_submissions.discard(px_pending)
                self.pending_since.pop(px_pending, None)

        open_levels = set(self.state.open_buy_price_to_id.keys())
        cooldown_prices: Set[float] = set()
        oid_to_price = {oid: px for px, oid in self.state.open_buy_price_to_id.items()}
        for oid in self.suspected_filled.keys():
            px = oid_to_price.get(oid)
            if px is not None:
                cooldown_prices.add(px)

        blocked = self.state.tp_blocked_entries

        # Extra safety: live snapshot to prevent exchange-hiccup duplicates
        live_buy_prices = set()
        try:
            if not self.settings.DRY_RUN:
                orders = self.broker.get_open_orders()
                for o in orders:
                    if str(o.get("side")) == "BUY" and str(o.get("status")) in ("NEW", "PARTIALLY_FILLED"):
                        ro = str(o.get("reduceOnly") or o.get("reduce_only") or "").lower() in ("true", "1")
                        if not ro:
                            live_buy_prices.add(self.broker.clamp_price(float(o.get("price", 0))))
        except Exception as e:
            dprint(f"[WARN] live snapshot failed: {e}")

        placed_now = 0

        for px in levels:
            if placed_now >= allowed:
                dprint(f"[STOP] Reached allowed cap this pass (placed_now={placed_now} / allowed={allowed})")
                break

            # --- Anti-dup / Guards ---
            if px in open_levels:
                dprint(f"[SKIP {px}] already in open_buy_price_to_id")
                continue
            if px in cooldown_prices:
                dprint(f"[SKIP {px}] in suspected_filled cooldown")
                continue
            if px in blocked:
                dprint(f"[SKIP {px}] TP-blocked entry (reduce-only SELL live)")
                continue
            if px in self.price_suppress_until:
                dprint(f"[SKIP {px}] suppressed until {self.price_suppress_until[px]:.1f}")
                continue
            if px in self.pending_submissions:
                dprint(f"[SKIP {px}] pending submission lock")
                continue
            if px in live_buy_prices:
                dprint(f"[SKIP {px}] live snapshot shows BUY already working")
                continue

            if not ignore_recent:
                if self._persistent_recent_hot(px, now_ts):
                    dprint(f"[SKIP {px}] persistent cooldown (recent_submissions)")
                    continue

            # Daily budget check
            est_cost = px * max(self.settings.QTY_PER_LADDER, self.broker.min_qty)
            if self.state.spent_today + est_cost > self.settings.MAX_DAILY_USDT:
                dprint(f"[SKIP {px}] MAX_DAILY_USDT would be exceeded (spent_today={self.state.spent_today:.2f}, est={est_cost:.2f})")
                continue

            # --- Submission ---
            self.pending_submissions.add(px)
            self.pending_since[px] = now_ts
            try:
                od = self.broker.limit_buy(px, self.settings.QTY_PER_LADDER)
                oid = str(od.get("orderId", "n/a"))

                self.state.open_buy_price_to_id[px] = oid
                self.state.total_buys += 1
                self.state.spent_today += est_cost
                self.state.recent_submissions[str(px)] = now_ts # Persisted cooldown

                self.state_manager.save_state()
                self.state_manager.log_trade("LIMIT_BUY_OPEN", px, self.settings.QTY_PER_LADDER, 0.0, f"orderId={oid}")
                send_telegram_message(self.settings, f"🚀 LIMIT BUY {self.settings.SYMBOL} @ {px:.4f} | Qty {self.settings.QTY_PER_LADDER:.4f}")

                placed_now += 1

            except Exception as e:
                dprint(f"[ERROR] limit_buy failed @ {px}: {e}")
                self.state_manager.log_trade("LIMIT_OPEN_ERROR", px, 0.0, 0.0, str(e))
            finally:
                self.pending_submissions.discard(px)
                self.pending_since.pop(px, None)

    # --- Fill Processing ---

    def on_buy_fill_confirmed(self, entry_price: float, qty: float, order_id: str):
        """Handles a confirmed BUY fill: opens TP and updates state."""
        if order_id in self.state.handled_fills:
            return
        self.state.handled_fills.add(order_id)
        
        try:
            entry_price = self.broker.clamp_price(entry_price)
            qty = self.broker.clamp_qty(qty)

            print(f"[FILL] BUY filled @ {entry_price} qty={qty} oid={order_id}")
            send_telegram_message(self.settings, f"🟢 BUY FILLED {self.settings.SYMBOL} @ {entry_price:.4f} | Qty {qty:.4f} | oid={order_id}")
            self.state_manager.log_trade("BUY_FILLED_CONFIRMED", entry_price, qty, 0.0, f"orderId={order_id}")

            # Open TP reduce-only
            cid = self.tp_client_id(entry_price, qty)
            od = self.broker.limit_tp_reduce(entry_price, qty, client_order_id=cid)
            tp_id = str(od.get("orderId", "n/a"))
            tp_price = self.broker.clamp_price(entry_price + self.settings.TAKE_PROFIT_USD)

            self.state.positions.append(Position(entry=entry_price, qty=qty, tp_price=tp_price, tp_id=tp_id))
            self.state.tp_blocked_entries.add(entry_price)

            print(f"[TP] OPEN reduce-only @ {tp_price} for entry {entry_price} qty={qty} (tp_id={tp_id})")
            send_telegram_message(self.settings, f"✅ TP OPEN {self.settings.SYMBOL} @ {tp_price:.4f} | Qty {qty:.4f}")
            self.state_manager.log_trade("LIMIT_TP_OPEN", tp_price, qty, 0.0, f"tpId={tp_id}")

            self.state_manager.save_state()
        except Exception as e:
            dprint(f"[ERROR] limit_tp_reduce failed @ entry {entry_price}: {e}")
            self.state_manager.log_trade("LIMIT_TP_ERROR", entry_price + self.settings.TAKE_PROFIT_USD, qty, 0.0, str(e))

    def on_tp_fill(self, entry_price: float, qty: float):
        """Handles a TP fill: cancels farthest BUY and triggers refill."""
        
        # Option-B: cancel farthest BUY on the book to keep depth constant
        if self.state.open_buy_price_to_id:
            far_px = min(self.state.open_buy_price_to_id.keys())
            far_oid = self.state.open_buy_price_to_id.get(far_px)
            try:
                if far_oid:
                    self.broker.cancel_order(far_oid)
            except Exception as e:
                self.state_manager.log_trade("CANCEL_FAR_ERROR", far_px, 0.0, 0.0, str(e))
            
            self.state.open_buy_price_to_id.pop(far_px, None)
            self.price_suppress_until[far_px] = max(self.price_suppress_until.get(far_px, 0.0), time.time() + self.settings.SUPPRESS_SEC_AFTER_CANCEL)

        self.state.tp_blocked_entries.discard(self.broker.clamp_price(entry_price))

        # Refill depth immediately after TP fill
        self.refill_now()

    def refill_now(self):
        """Refill grid immediately (single pass) – used right after a BUY fill or TP fill."""
        self.sync_open_from_exchange_full()
        levels = self.build_grid_candidates(self.state.base_price)
        if len(self.state.open_buy_price_to_id) < self.settings.MAX_LADDERS:
            self.place_missing_buys(levels, ignore_recent=True)
            self.state_manager.save_state()

    def process_positions_vs_market(self, bid: float):
        """Checks if any TP targets have been hit by the current bid price."""
        remaining: List[Position] = []
        for lot in self.state.positions:
            entry = lot.entry
            qty = lot.qty
            tp_price = lot.tp_price
            
            if bid >= tp_price:
                # TP hit
                pnl_gross = (tp_price - entry) * qty
                
                # Use broker's actual taker fee if available, otherwise use settings default
                taker_fee = self.broker.taker_fee if self.broker.taker_fee is not None else self.settings.TAKER_FEE
                
                fee_open = entry * qty * taker_fee
                fee_close = tp_price * qty * taker_fee
                pnl = pnl_gross - (fee_open + fee_close)
                
                self.state.realized_pnl += pnl
                self.state.total_sells += 1
                
                self.state_manager.log_trade("TP_FILLED", tp_price, qty, pnl, f"entry={entry}")
                send_telegram_message(self.settings, f"✅ GRID CLOSE PnL +${pnl:.2f} (Total ${self.state.realized_pnl:.2f}) | {entry:.4f}→{tp_price:.4f}")
                
                self.on_tp_fill(entry, qty)
            else:
                remaining.append(lot)
        
        self.state.positions = remaining
        if len(remaining) != len(self.state.positions):
            self.state_manager.save_state()

    # --- Fill Detection ---

    def confirm_and_process_vanished(self, vanished: List[Tuple[float, str]]):
        """Checks orders that vanished from the open orders list (filled/canceled)."""
        now = time.time()

        for price, oid in vanished:
            # Remove from local map temporarily
            self.state.open_buy_price_to_id.pop(price, None)

            # Instant refill path (no debounce)
            if self.settings.INSTANT_TP_REFILL:
                od = self.broker.get_order(oid)
                if od is None:
                    self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                    continue

                status = str(od.get("status", "")).upper()
                
                if status == "FILLED":
                    if oid in self.state.handled_fills:
                        self.refill_now()
                        continue

                    try:
                        exec_qty = float(od.get("executedQty", "0") or "0")
                    except Exception:
                        exec_qty = 0.0

                    want_qty = max(self.settings.QTY_PER_LADDER, 0.0)
                    if exec_qty >= want_qty * 0.999:
                        self.on_buy_fill_confirmed(price, self.settings.QTY_PER_LADDER, oid)
                        self.refill_now()
                    else:
                        self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                    continue

                elif status in ("CANCELED", "EXPIRED", "REJECTED"):
                    self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_AFTER_CANCEL)
                    self.state_manager.log_trade("BUY_CANCELED_OR_EXPIRED", price, 0.0, 0.0, f"orderId={oid}, status={status}")
                    continue

                elif status in ("NOT_FOUND", "UNKNOWN"):
                    self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                    continue

                elif status in ("NEW", "PARTIALLY_FILLED"):
                    # Order is actually still alive, restore to map
                    self.state.open_buy_price_to_id[price] = oid
                    continue

                else:
                    self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                    self.state_manager.log_trade("BUY_UNKNOWN_STATUS_REMOVED", price, 0.0, 0.0, f"orderId={oid}, status={status}")
                    continue

            # Old path (with debounce) if INSTANT_TP_REFILL=False
            first = self.suspected_filled.get(oid)
            if first is None:
                self.suspected_filled[oid] = now
                self.state.open_buy_price_to_id[price] = oid # Restore to map for debounce period
                continue
            if now - first < 2.0:
                self.state.open_buy_price_to_id[price] = oid # Restore to map for debounce period
                continue

            # Debounce period passed, check status
            od = self.broker.get_order(oid)
            if od is None:
                self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                self.suspected_filled.pop(oid, None)
                continue

            status = str(od.get("status", ""))
            self.suspected_filled.pop(oid, None)

            if status.upper() == "FILLED":
                if oid in self.state.handled_fills:
                    continue
                try:
                    exec_qty = float(od.get("executedQty", "0") or "0")
                except Exception:
                    exec_qty = 0.0
                if exec_qty >= max(self.settings.QTY_PER_LADDER, 0.0) * 0.999:
                    self.on_buy_fill_confirmed(price, self.settings.QTY_PER_LADDER, oid)
                else:
                    self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                    self.state_manager.log_trade("BUY_PARTIAL_OR_ZERO_EXEC", price, 0.0, 0.0, f"orderId={oid}, executedQty={od.get('executedQty')}")
            elif status.upper() in ("CANCELED", "EXPIRED", "REJECTED"):
                self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_AFTER_CANCEL)
                self.state_manager.log_trade("BUY_CANCELED_OR_EXPIRED", price, 0.0, 0.0, f"orderId={oid}, status={status}")
            elif status.upper() in ("NOT_FOUND", "UNKNOWN"):
                self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
            elif status.upper() in ("NEW", "PARTIALLY_FILLED"):
                self.state.open_buy_price_to_id[price] = oid # Restore to map
            else:
                self.price_suppress_until[price] = max(self.price_suppress_until.get(price, 0.0), now + self.settings.SUPPRESS_SEC_ON_UNKNOWN)
                self.state_manager.log_trade("BUY_UNKNOWN_STATUS_REMOVED", price, 0.0, 0.0, f"orderId={oid}, status={status}")
        
        self.state_manager.save_state()


    def detect_filled_buys_and_restore(self):
        """Compares local open BUY map against live exchange orders to find vanished orders."""
        if not self.broker or self.settings.DRY_RUN:
            return
        try:
            orders = self.broker.get_open_orders()
        except Exception as e:
            print(f"[WARN] get_open_orders failed: {e}")
            return

        live_ids: Set[str] = set()
        for o in orders:
            side = str(o.get("side"))
            st = str(o.get("status", ""))
            reduce_only = str(o.get("reduceOnly") or o.get("reduce_only") or o.get("reduce_only_flag") or "").lower() in ("true", "1")
            if side == "BUY" and not reduce_only and st in ("NEW", "PARTIALLY_FILLED"):
                oid = str(o.get("orderId", ""))
                live_ids.add(oid)

        vanished = []
        for px, oid in list(self.state.open_buy_price_to_id.items()):
            if oid not in live_ids:
                vanished.append((px, oid))

        if vanished:
            dprint(f"[CHECK] vanished candidates: {vanished}")
            self.confirm_and_process_vanished(vanished)

    # --- Trailing ---

    def reanchor_up_if_needed(self, mid: float):
        """Adjusts the base price upwards if trailing is enabled and conditions are met."""
        if not self.settings.TRAIL_UP:
            return
        
        target_base = align_to_grid(mid, self.settings.GRID_STEP_USD)
        
        if target_base < self.state.base_price + self.settings.GRID_STEP_USD * self.settings.TRAIL_TRIGGER_STEPS:
            return

        steps_up = int((target_base - self.state.base_price) / self.settings.GRID_STEP_USD)
        if steps_up <= 0:
            return

        new_base = self.state.base_price + steps_up * self.settings.GRID_STEP_USD
        new_low = new_base - self.settings.GRID_STEP_USD * self.settings.MAX_LADDERS

        cancels = 0
        for px, oid in sorted(list(self.state.open_buy_price_to_id.items())):
            if px < new_low:
                try:
                    if oid:
                        self.broker.cancel_order(oid)
                        dprint(f"[REANCHOR] cancel BUY {oid} at {px} (below new_low {new_low})")
                except Exception as e:
                    self.state_manager.log_trade("TRAIL_CANCEL_ERROR", px, 0.0, 0.0, str(e))
                
                self.state.open_buy_price_to_id.pop(px, None)
                self.price_suppress_until[px] = max(self.price_suppress_until.get(px, 0.0), time.time() + self.settings.SUPPRESS_SEC_AFTER_CANCEL)
                cancels += 1
                if cancels >= self.settings.TRAIL_MAX_CANCEL_PER_REANCHOR:
                    break

        self.state.base_price = new_base
        self.state_manager.log_trade("REANCHOR_UP", self.state.base_price, 0.0, 0.0, f"steps={steps_up}")
        send_telegram_message(self.settings, f"↗️ RE-ANCHOR BASE to {self.state.base_price:.0f} (steps {steps_up})")

        self.sync_open_from_exchange_full()
        levels = self.build_grid_candidates(self.state.base_price)
        if not self.state.HALT_PLACEMENT:
            self.place_missing_buys(levels)
            self.state_manager.save_state()