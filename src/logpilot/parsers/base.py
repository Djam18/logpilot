"""Abstract base parser — all parsers implement this Protocol."""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable


LogEntry = dict[str, object]


@runtime_checkable
class LogParser(Protocol):
    """Protocol for log parsers — duck-typed, no inheritance required."""

    def parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line. Returns None if the line should be skipped."""
        ...

    def parse_file(self, path: str) -> Iterator[LogEntry]:
        """Stream-parse a log file line by line."""
        ...

    @property
    def name(self) -> str:
        """Human-readable parser name (e.g. 'json', 'apache-combined')."""
        ...
