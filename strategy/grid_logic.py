"""Core grid strategy logic (pure functions).

Keep this module free of side-effects so it can be tested easily.
"""
from typing import List


def compute_grid_levels(mid_price: float, grid_size: int, spacing: float) -> List[float]:
    """Compute `grid_size` price levels centered around `mid_price` with `spacing`.

    The return value is a sorted list of prices (ascending).

    Args:
        mid_price: center price (float)
        grid_size: total number of grid levels (int, must be >= 1)
        spacing: difference between successive levels

    Returns:
        List[float]: sorted price levels
    """
    if grid_size <= 0:
        raise ValueError("grid_size must be >= 1")
    if spacing <= 0:
        raise ValueError("spacing must be > 0")

    # If grid_size is odd, include the mid_price as a level.
    half = grid_size // 2
    levels: List[float] = []
    # generate levels from -half..+half
    start = -half
    for i in range(grid_size):
        level = mid_price + (start + i) * spacing
        levels.append(round(level, 8))
    levels.sort()
    return levels


__all__ = ["compute_grid_levels"]
