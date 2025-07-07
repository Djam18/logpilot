"""Count log entries by a field value."""
from __future__ import annotations

from collections import Counter as _Counter
from typing import Any


class Counter:
    """Count occurrences of a field value across log entries."""

    def __init__(self, field: str) -> None:
        self._field = field
        self._counts: _Counter[str] = _Counter()

    def add(self, entry: dict[str, Any]) -> None:
        value = str(entry.get(self._field, "unknown"))
        self._counts[value] += 1

    def top(self, n: int = 10) -> list[tuple[str, int]]:
        return self._counts.most_common(n)

    @property
    def total(self) -> int:
        return sum(self._counts.values())
