"""Basic tests for strategy/grid_logic.py"""
import pytest

from gridbot.strategy.grid_logic import compute_grid_levels


def test_compute_grid_levels_basic():
    mid = 100.0
    levels = compute_grid_levels(mid, grid_size=5, spacing=1.0)
    # for grid_size=5 with spacing=1 -> levels = [98,99,100,101,102]
    assert levels == [98.0, 99.0, 100.0, 101.0, 102.0]


def test_invalid_args():
    with pytest.raises(ValueError):
        compute_grid_levels(100.0, grid_size=0, spacing=1.0)
    with pytest.raises(ValueError):
        compute_grid_levels(100.0, grid_size=3, spacing=0)
