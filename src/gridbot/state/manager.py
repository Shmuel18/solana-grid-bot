import os
import json
import csv
import datetime
import shutil
import pathlib
import time
from typing import Dict, List, Set, Optional
from json import JSONDecodeError
from dataclasses import dataclass, field, asdict

from gridbot.config.settings import Settings
from gridbot.core.utils import dprint

@dataclass
class Position:
    entry: float
    qty: float
    tp_price: float
    tp_id: str

@dataclass
class BotState:
    # Core State
    base_price: float = 0.0
    positions: List[Position] = field(default_factory=list)
    realized_pnl: float = 0.0
    total_buys: int = 0
    total_sells: int = 0

    # Daily Budget
    spent_today: float = 0.0
    spent_date: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d"))

    # Live Maps
    open_buy_price_to_id: Dict[float, str] = field(default_factory=dict)
    tp_blocked_entries: Set[float] = field(default_factory=set) # Derived, not persisted

    # Fill Tracking
    handled_fills: Set[str] = field(default_factory=set)
    recent_submissions: Dict[str, float] = field(default_factory=dict) # key=str(price), value=unix_ts

    # Control
    HALT_PLACEMENT: bool = False

    def __post_init__(self):
        # Ensure sets are initialized correctly from loaded data if needed
        self.handled_fills = set(self.handled_fills)
        self.tp_blocked_entries = set(self.tp_blocked_entries)

class StateManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = BotState()
        self.csv_file = settings.CSV_FILE
        self.state_file = settings.STATE_FILE

    def init_csv(self):
        new = not os.path.exists(self.csv_file)
        with open(self.csv_file, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time","event","price","qty","pnl","total_pnl","note"])

    def log_trade(self, event: str, price: float, qty: float = 0.0, pnl: float = 0.0, note: str = ""):
        with open(self.csv_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                datetime.datetime.now().isoformat(timespec="seconds"),
                event, price, qty, pnl, self.state.realized_pnl, note
            ])

    def save_state(self):
        s = asdict(self.state)
        # Convert non-serializable types for JSON
        s["positions"] = [asdict(p) for p in self.state.positions]
        s["open_buy_price_to_id"] = {str(k): v for k, v in self.state.open_buy_price_to_id.items()}
        s["handled_fills"] = list(self.state.handled_fills)
        s.pop("tp_blocked_entries", None) # Do not persist derived state

        tmp = self.state_file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, separators=(",", ":"), indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_file)
        except Exception as e:
            dprint(f"[ERROR] Failed to save state: {e}")

    def load_state(self) -> bool:
        p = pathlib.Path(self.state_file)
        if not p.exists():
            return False
        try:
            if p.stat().st_size < 2:
                backup = p.with_suffix(".json.empty.bak")
                shutil.move(str(p), str(backup))
                print(f"[WARN] state file was empty -> moved to {backup.name}")
                return False

            with p.open("r", encoding="utf-8") as f:
                s = json.load(f)

            # Load core state
            self.state.base_price = float(s.get("base_price", 0.0))
            self.state.realized_pnl = float(s.get("realized_pnl", 0.0))
            self.state.total_buys = int(s.get("total_buys", 0))
            self.state.total_sells = int(s.get("total_sells", 0))
            self.state.spent_today = float(s.get("spent_today", 0.0))
            self.state.spent_date = s.get("spent_date", self.state.spent_date)

            # Load complex types
            self.state.positions = [Position(**p) for p in s.get("positions", [])]
            self.state.open_buy_price_to_id = {float(k): str(v) for k, v in s.get("open_buy_price_to_id", {}).items()}
            self.state.handled_fills = set(s.get("handled_fills", []))
            self.state.recent_submissions = dict(s.get("recent_submissions", {}))

            # Daily reset check
            curr = datetime.datetime.now().strftime("%Y-%m-%d")
            if curr != self.state.spent_date:
                self.state.spent_today = 0.0
                self.state.spent_date = curr

            print(f"[STATE] Loaded. Positions: {len(self.state.positions)} | open-buy map: {len(self.state.open_buy_price_to_id)} | handled_fills={len(self.state.handled_fills)}")
            return True

        except (JSONDecodeError, ValueError, TypeError) as e:
            backup = p.with_suffix(".json.corrupt.bak")
            shutil.move(str(p), str(backup))
            print(f"[WARN] load_state: corrupt JSON ({e}). Moved to {backup.name}. Starting fresh.")
            return False
        except Exception as e:
            print(f"[WARN] load_state failed: {e}")
            return False