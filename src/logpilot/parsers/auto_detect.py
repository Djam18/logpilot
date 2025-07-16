"""Auto-detect log format from content heuristics."""
from __future__ import annotations

import re
from typing import Iterator

from .apache import ApacheParser
from .base import LogEntry, LogParser
from .json_parser import JsonParser
from .syslog import SyslogParser

# Syslog month abbreviation pattern (RFC 3164 timestamp start)
_SYSLOG_MONTH_RE = re.compile(
    r"^(?:<\d+>)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s"
)

# Apache Combined Log: starts with an IP or hostname, has [timestamp]
_APACHE_RE = re.compile(r"^\S+ \S+ \S+ \[")


def detect_format(line: str) -> str:
    """Return the format name detected from a single sample line.

    Returns one of: 'json', 'apache', 'syslog', 'raw'.
    """
    line = line.strip()
    if not line:
        return "raw"
    if line.startswith("{"):
        return "json"
    if _APACHE_RE.match(line):
        return "apache"
    if _SYSLOG_MONTH_RE.match(line):
        return "syslog"
    return "raw"


class AutoDetectParser:
    """Detect log format from content heuristics and delegate to the right parser.

    Detection order (first match wins):
      1. JSON   — line starts with '{'
      2. Apache — IP/host + [timestamp] pattern
      3. Syslog — RFC 3164 month-day timestamp
      4. raw    — fallback, emit as {'message': line, 'raw': True}
    """

    def __init__(self, hint: str = "auto") -> None:
        self._hint = hint
        self._parsers: dict[str, LogParser] = {
            "json": JsonParser(),
            "apache": ApacheParser(),
            "syslog": SyslogParser(),
        }

    @property
    def name(self) -> str:
        return "auto"

    def parse_line(self, line: str) -> LogEntry | None:
        line = line.strip()
        if not line:
            return None
        fmt = detect_format(line)
        parser = self._parsers.get(fmt)
        if parser is not None:
            return parser.parse_line(line)
        return {"message": line, "raw": True}

    def parse_file(self, path: str) -> Iterator[LogEntry]:
        """Stream-parse a file, auto-detecting format from the first non-empty line.

        The detected format is locked in for the entire file — no per-line
        re-detection overhead on large files.
        """
        locked_parser: LogParser | None = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                if locked_parser is None:
                    fmt = detect_format(stripped)
                    locked_parser = self._parsers.get(fmt)
                if locked_parser is not None:
                    entry = locked_parser.parse_line(stripped)
                else:
                    entry = {"message": stripped, "raw": True}
                if entry is not None:
                    yield entry
