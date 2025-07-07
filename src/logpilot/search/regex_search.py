"""Regex-based log search."""
from __future__ import annotations

import re
from typing import Any


class RegexSearch:
    """Search log entries using a compiled regex pattern."""

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self._regex = re.compile(pattern, flags)

    def matches(self, entry: dict[str, Any]) -> bool:
        """Return True if any field value matches the pattern."""
        return any(self._regex.search(str(v)) for v in entry.values())
