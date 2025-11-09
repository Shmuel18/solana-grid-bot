from typing import List

def compute_grid_levels(mid: float, grid_size: int, spacing: float) -> List[float]:
    """
    Computes a list of grid levels centered around mid.
    Assumes grid_size is an odd number for perfect centering.
    """
    if grid_size <= 0 or spacing <= 0:
        raise ValueError("grid_size and spacing must be positive")
    
    # Calculate how many steps away from the center the lowest level is
    half_size = (grid_size - 1) // 2
    
    levels = []
    for i in range(-half_size, half_size + 1):
        levels.append(mid + i * spacing)
        
    # Ensure floating point precision is handled for comparison in tests
    return [round(level, 10) for level in levels]