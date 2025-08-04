"""Numeric percentile calculation over a log field."""
from __future__ import annotations

import math
from typing import Any


def _percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile for a pre-sorted list."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    rank = math.ceil(p / 100 * n) - 1
    return sorted_values[max(0, min(rank, n - 1))]


class Percentiles:
    """Collect a numeric field and compute percentile statistics.

    Usage::

        p = Percentiles("bytes")
        for entry in entries:
            p.add(entry)

        print(p.summary())
        # {'p50': 1234.0, 'p90': 5678.0, 'p95': 7890.0, 'p99': 9012.0,
        #  'min': 10.0, 'max': 99999.0, 'mean': 2345.6, 'count': 1000}
    """

    def __init__(self, field: str) -> None:
        self._field = field
        self._values: list[float] = []
        self._dirty = True
        self._sorted: list[float] = []

    def add(self, entry: dict[str, Any]) -> None:
        raw = entry.get(self._field)
        if raw is None:
            return
        try:
            self._values.append(float(raw))
            self._dirty = True
        except (TypeError, ValueError):
            pass

    def _ensure_sorted(self) -> None:
        if self._dirty:
            self._sorted = sorted(self._values)
            self._dirty = False

    def percentile(self, p: float) -> float:
        self._ensure_sorted()
        return _percentile(self._sorted, p)

    def summary(
        self, percentiles: list[float] | None = None
    ) -> dict[str, float]:
        self._ensure_sorted()
        ps = percentiles or [50, 90, 95, 99]
        result: dict[str, float] = {f"p{int(p)}": _percentile(self._sorted, p) for p in ps}
        if self._sorted:
            result["min"] = self._sorted[0]
            result["max"] = self._sorted[-1]
            result["mean"] = sum(self._sorted) / len(self._sorted)
        result["count"] = float(len(self._sorted))
        return result

    def __len__(self) -> int:
        return len(self._values)
