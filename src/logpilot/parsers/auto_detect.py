"""Auto-detect log format from content."""
from __future__ import annotations

from typing import Iterator

from .base import LogEntry
from .json_parser import JsonParser


class AutoDetectParser:
    """Detect and delegate to the appropriate parser."""

    def __init__(self, hint: str = "auto") -> None:
        self._hint = hint
        self._parsers = {"json": JsonParser()}

    @property
    def name(self) -> str:
        return "auto"

    def parse_line(self, line: str) -> LogEntry | None:
        line = line.strip()
        if not line:
            return None
        # JSON detection: starts with {
        if line.startswith("{"):
            return self._parsers["json"].parse_line(line)
        # Fallback: treat as raw text
        return {"message": line, "raw": True}

    def parse_file(self, path: str) -> Iterator[LogEntry]:
        """Stream-parse, auto-detecting format from first non-empty line."""
        parser = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if parser is None:
                    parser = self._detect_format(line)
                entry = parser.parse_line(line)
                if entry is not None:
                    yield entry

    def _detect_format(self, sample: str) -> JsonParser:
        if sample.strip().startswith("{"):
            return self._parsers["json"]
        return self._parsers["json"]  # fallback
