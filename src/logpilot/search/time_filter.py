"""Time-range filtering for log entries."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

# Formats tried in order when parsing log timestamps
_TIMESTAMP_FORMATS: list[str] = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",  # Apache Combined
    "%b %d %H:%M:%S",         # Syslog (no year)
    "%Y-%m-%d",
]


def _parse_timestamp(raw: str) -> datetime | None:
    """Try each known format and return the first successful parse."""
    raw = raw.strip()
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


class TimeRangeFilter:
    """Filter log entries to those whose timestamp falls within [start, end].

    Either bound may be ``None`` (open interval).
    """

    def __init__(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        timestamp_key: str = "timestamp",
    ) -> None:
        self.start = start
        self.end = end
        self._key = timestamp_key

    def matches(self, entry: dict[str, Any]) -> bool:
        raw = entry.get(self._key)
        if raw is None:
            return False
        ts = _parse_timestamp(str(raw))
        if ts is None:
            return False
        # Strip tzinfo for naive comparison if needed
        ts_naive = ts.replace(tzinfo=None)
        if self.start and ts_naive < self.start.replace(tzinfo=None):
            return False
        if self.end and ts_naive > self.end.replace(tzinfo=None):
            return False
        return True

    def filter(
        self, entries: Iterator[dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        """Yield entries whose timestamp falls within the configured range."""
        for entry in entries:
            if self.matches(entry):
                yield entry
