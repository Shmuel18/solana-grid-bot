"""Simple state manager for saving/loading bot state (JSON).

Implements atomic save (write to temp file then replace) to reduce risk of
corruption on crashes.
"""
import json
import os
from typing import Any


def save_state(path: str, state: Any) -> None:
    """Save `state` (serializable) to `path` atomically."""
    dirpath = os.path.dirname(os.path.abspath(path))
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def load_state(path: str, default: Any = None) -> Any:
    """Load JSON state from `path`. Return `default` if file missing or bad."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        # If the file is corrupted, propagate or return default per needs.
        return default


__all__ = ["save_state", "load_state"]
