"""Apache Common and Combined log format parser.

Common:  %h %l %u %t "%r" %>s %b
Combined: Common + "%{Referer}i" "%{User-agent}i"
"""
from __future__ import annotations

import re
from typing import Iterator

from .base import LogEntry

# Apache Combined Log Format regex
_COMBINED_RE = re.compile(
    r'(?P<host>\S+)\s+'           # client IP
    r'(?P<ident>\S+)\s+'          # ident
    r'(?P<user>\S+)\s+'           # user
    r'\[(?P<time>[^\]]+)\]\s+'    # [timestamp]
    r'"(?P<request>[^"]+)"\s+'    # "METHOD /path HTTP/x.x"
    r'(?P<status>\d+)\s+'         # status code
    r'(?P<bytes>\S+)'             # bytes sent
    r'(?:\s+"(?P<referer>[^"]*)")?' # optional referer
    r'(?:\s+"(?P<agent>[^"]*)")?'   # optional user-agent
)


class ApacheParser:
    """Parse Apache Common and Combined log formats."""

    @property
    def name(self) -> str:
        return "apache"

    def parse_line(self, line: str) -> LogEntry | None:
        line = line.strip()
        if not line:
            return None
        m = _COMBINED_RE.match(line)
        if not m:
            return None
        d = m.groupdict()
        # Parse request into method/path/protocol
        request_parts = (d.get("request") or "").split(" ", 2)
        return {
            "host": d.get("host"),
            "timestamp": d.get("time"),
            "method": request_parts[0] if len(request_parts) > 0 else None,
            "path": request_parts[1] if len(request_parts) > 1 else None,
            "protocol": request_parts[2] if len(request_parts) > 2 else None,
            "status": int(d["status"]) if d.get("status", "").isdigit() else None,
            "bytes": int(d["bytes"]) if (d.get("bytes") or "-") != "-" else 0,
            "referer": d.get("referer"),
            "user_agent": d.get("agent"),
            "level": "ERROR" if int(d.get("status", 0) or 0) >= 500 else "INFO",
        }

    def parse_file(self, path: str) -> Iterator[LogEntry]:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = self.parse_line(line)
                if entry is not None:
                    yield entry
