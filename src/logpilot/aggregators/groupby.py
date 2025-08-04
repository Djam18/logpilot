"""Group log entries by a field value."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class GroupBy:
    """Bucket log entries by the value of a given field.

    Usage::

        gb = GroupBy("level")
        for entry in entries:
            gb.add(entry)

        for level, bucket in gb.items():
            print(level, len(bucket))
    """

    def __init__(self, field: str) -> None:
        self._field = field
        self._groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, entry: dict[str, Any]) -> None:
        key = str(entry.get(self._field, "unknown"))
        self._groups[key].append(entry)

    def get(self, key: str) -> list[dict[str, Any]]:
        return self._groups.get(key, [])

    def keys(self) -> list[str]:
        return sorted(self._groups.keys())

    def items(self) -> list[tuple[str, list[dict[str, Any]]]]:
        return [(k, self._groups[k]) for k in self.keys()]

    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._groups.items()}

    def __len__(self) -> int:
        return len(self._groups)

    def __repr__(self) -> str:
        return f"GroupBy(field={self._field!r}, groups={len(self._groups)})"
