"""Syslog format parser (RFC 3164 and RFC 5424)."""
from __future__ import annotations

import re
from typing import Iterator

from .base import LogEntry

# RFC 3164: <priority>timestamp hostname tag: message
_SYSLOG_RE = re.compile(
    r"^(?:<(?P<priority>\d+)>)?"
    r"(?P<timestamp>\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<tag>[^:\[]+)(?:\[(?P<pid>\d+)\])?:\s*"
    r"(?P<message>.*)$"
)

_SEVERITY = {
    0: "EMERG", 1: "ALERT", 2: "CRIT", 3: "ERROR",
    4: "WARN", 5: "NOTICE", 6: "INFO", 7: "DEBUG",
}


class SyslogParser:
    """Parse RFC 3164 syslog format."""

    @property
    def name(self) -> str:
        return "syslog"

    def parse_line(self, line: str) -> LogEntry | None:
        line = line.strip()
        if not line:
            return None
        m = _SYSLOG_RE.match(line)
        if not m:
            return {"message": line, "raw": True}
        d = m.groupdict()
        priority = int(d["priority"]) if d.get("priority") else None
        severity = _SEVERITY.get(priority % 8, "INFO") if priority is not None else "INFO"
        return {
            "timestamp": d.get("timestamp"),
            "hostname": d.get("hostname"),
            "tag": d.get("tag", "").strip(),
            "pid": d.get("pid"),
            "message": d.get("message", ""),
            "level": severity,
            "priority": priority,
        }

    def parse_file(self, path: str) -> Iterator[LogEntry]:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = self.parse_line(line)
                if entry is not None:
                    yield entry
