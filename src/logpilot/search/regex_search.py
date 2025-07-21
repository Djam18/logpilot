"""Regex-based log search with optional field targeting."""
from __future__ import annotations

import re
from typing import Any


class RegexSearch:
    """Search log entries using a compiled regex pattern.

    By default, all field values are tested.  Pass ``fields`` to restrict
    matching to a specific subset of keys (e.g. ``fields=["message"]``).
    """

    def __init__(
        self,
        pattern: str,
        flags: int = re.IGNORECASE,
        fields: list[str] | None = None,
    ) -> None:
        self._regex = re.compile(pattern, flags)
        self._fields = fields

    def matches(self, entry: dict[str, Any]) -> bool:
        """Return True if the pattern matches any relevant field value."""
        if self._fields:
            values = (entry[k] for k in self._fields if k in entry)
        else:
            values = entry.values()  # type: ignore[assignment]
        return any(self._regex.search(str(v)) for v in values)

    def filter(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return the subset of entries that match."""
        return [e for e in entries if self.matches(e)]
