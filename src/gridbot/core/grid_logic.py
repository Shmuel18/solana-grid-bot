"""Grid trading logic and position management."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Dict, List, Optional, Tuple

from ..broker.binance_connector import BinanceConnector
from ..config.settings import config
from ..state.manager import save_state
from .utils import log_trade, spread_bps


def compute_grid_levels(mid_price: float, grid_size: int, spacing: float) -> List[float]:
    """Compute grid levels around mid price."""
    levels = []
    for i in range(-grid_size, grid_size + 1):
        level = mid_price + (i * spacing)
        levels.append(level)
    return sorted(levels)


def align_to_grid(mid: float, step: float, mode: str) -> float:
    """Align price to grid step with directional rounding."""
    if step <= 0:
        return mid
    dm = Decimal(str(mid))
    ds = Decimal(str(step))
    rounding_mode = ROUND_FLOOR if mode == 'LONG_ONLY' else ROUND_CEILING
    num_steps = (dm / ds)
    aligned = num_steps.to_integral_value(rounding=rounding_mode) * ds
    return float(aligned)


def _ensure_min_notional_and_cap(broker: BinanceConnector, trade_price: float, qty: float,
                                spent_today: float) -> Optional[Tuple[float, float]]:
    """
    Validate qty meets MIN_NOTIONAL and max daily spend requirements.
    Returns (qty, est_cost) or None if not viable.
    """
    qty = broker.clamp_qty(qty)
    notional = trade_price * qty

    if broker.min_notional and notional < broker.min_notional:
        required = broker.min_notional + broker.tick_size
        req_qty = required / trade_price
        req_qty = broker.clamp_qty(req_qty)
        est_cost = trade_price * req_qty
        if spent_today + est_cost > config.max_daily_usdt:
            return None
        if req_qty <= 0:
            return None
        return req_qty, est_cost

    est_cost = trade_price * qty
    if spent_today + est_cost > config.max_daily_usdt:
        return None
    return qty, est_cost