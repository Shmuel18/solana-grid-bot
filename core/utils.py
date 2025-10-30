"""Helper utilities: rounding, CSV append, simple formatting."""
import csv
import os
from decimal import Decimal, ROUND_DOWN
from typing import Iterable


def round_price(price: float, decimals: int = 8) -> float:
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(price).quantize(q, rounding=ROUND_DOWN)
    return float(d)


def append_csv_row(path: str, row: Iterable) -> None:
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            # no-op header expectation; caller should handle header
            pass
        writer.writerow(row)


__all__ = ["round_price", "append_csv_row"]
