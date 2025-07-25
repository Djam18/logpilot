"""Composable filter chain for log entries.

Filters are callables that accept a log-entry dict and return bool.
Chains short-circuit on the first failing predicate (AND semantics).
"""
from __future__ import annotations

from typing import Any, Callable, Iterator

Predicate = Callable[[dict[str, Any]], bool]


class FilterChain:
    """Apply multiple predicates in sequence (logical AND).

    Usage::

        chain = FilterChain()
        chain.add(RegexSearch("ERROR").matches)
        chain.add(TimeRangeFilter(start=t0, end=t1).matches)

        results = list(chain.apply(entries))
    """

    def __init__(self) -> None:
        self._predicates: list[Predicate] = []

    def add(self, predicate: Predicate) -> "FilterChain":
        """Append a predicate and return self for chaining."""
        self._predicates.append(predicate)
        return self

    def matches(self, entry: dict[str, Any]) -> bool:
        """Return True if all predicates accept the entry."""
        return all(p(entry) for p in self._predicates)

    def apply(
        self, entries: Iterator[dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        """Yield entries that pass every predicate."""
        for entry in entries:
            if self.matches(entry):
                yield entry

    # Allow combining two chains with &
    def __and__(self, other: "FilterChain") -> "FilterChain":
        combined = FilterChain()
        combined._predicates = self._predicates + other._predicates
        return combined

    def __len__(self) -> int:
        return len(self._predicates)

    def __repr__(self) -> str:
        return f"FilterChain({len(self._predicates)} predicates)"


class AnyFilter:
    """Logical OR: accept entry if at least one predicate matches."""

    def __init__(self, *predicates: Predicate) -> None:
        self._predicates = list(predicates)

    def matches(self, entry: dict[str, Any]) -> bool:
        return any(p(entry) for p in self._predicates)

    def apply(
        self, entries: Iterator[dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        for entry in entries:
            if self.matches(entry):
                yield entry
