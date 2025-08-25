"""Shared pytest fixtures for logpilot tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_log_file(tmp_path: Path):
    """Return a factory that creates temporary log files."""

    def _make(lines: list[str], name: str = "test.log") -> Path:
        p = tmp_path / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    return _make


@pytest.fixture()
def json_log_lines() -> list[str]:
    return [
        json.dumps({"timestamp": "2025-08-01T10:00:00", "level": "INFO", "message": "startup"}),
        json.dumps({"timestamp": "2025-08-01T10:00:01", "level": "ERROR", "message": "disk full"}),
        json.dumps({"timestamp": "2025-08-01T10:00:02", "level": "WARN", "message": "retry"}),
        json.dumps({"timestamp": "2025-08-01T10:00:03", "level": "INFO", "message": "done"}),
    ]


@pytest.fixture()
def apache_log_lines() -> list[str]:
    return [
        '192.168.1.1 - - [01/Aug/2025:10:00:00 +0000] "GET /api/v1/health HTTP/1.1" 200 512',
        '10.0.0.1 - bob [01/Aug/2025:10:00:01 +0000] "POST /api/v1/jobs HTTP/1.1" 201 1024',
        '192.168.1.2 - - [01/Aug/2025:10:00:02 +0000] "GET /missing HTTP/1.1" 404 128',
    ]


@pytest.fixture()
def syslog_lines() -> list[str]:
    return [
        "Aug  1 10:00:00 webserver sshd[1234]: Accepted publickey for admin",
        "Aug  1 10:00:01 webserver kernel: Out of memory: Kill process 5678",
        "Aug  1 10:00:02 webserver cron[9999]: (root) CMD (/usr/bin/backup.sh)",
    ]
