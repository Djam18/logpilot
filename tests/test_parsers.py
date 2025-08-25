"""Tests for all log parsers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from logpilot.parsers.auto_detect import AutoDetectParser, detect_format
from logpilot.parsers.apache import ApacheParser
from logpilot.parsers.json_parser import JsonParser
from logpilot.parsers.syslog import SyslogParser


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    ('{"level": "INFO"}', "json"),
    ('192.168.1.1 - - [01/Aug/2025:10:00:00 +0000] "GET / HTTP/1.1" 200 512', "apache"),
    ("Aug  1 10:00:00 host sshd[123]: message", "syslog"),
    ("Jan 15 08:30:00 server app: started", "syslog"),
    ("plain text log line", "raw"),
    ("", "raw"),
])
def test_detect_format(line: str, expected: str) -> None:
    assert detect_format(line) == expected


# ---------------------------------------------------------------------------
# JsonParser
# ---------------------------------------------------------------------------

class TestJsonParser:
    def test_valid_json_line(self) -> None:
        p = JsonParser()
        entry = p.parse_line('{"level": "ERROR", "message": "oops"}')
        assert entry is not None
        assert entry["level"] == "ERROR"

    def test_invalid_json_returns_none(self) -> None:
        p = JsonParser()
        assert p.parse_line("not json") is None

    def test_empty_line_returns_none(self) -> None:
        p = JsonParser()
        assert p.parse_line("") is None

    def test_parse_file_streams(self, tmp_log_file, json_log_lines) -> None:
        path = tmp_log_file(json_log_lines)
        p = JsonParser()
        entries = list(p.parse_file(str(path)))
        assert len(entries) == 4
        assert entries[1]["level"] == "ERROR"


# ---------------------------------------------------------------------------
# ApacheParser
# ---------------------------------------------------------------------------

class TestApacheParser:
    def test_valid_apache_line(self, apache_log_lines) -> None:
        p = ApacheParser()
        entry = p.parse_line(apache_log_lines[0])
        assert entry is not None
        assert entry["status"] == 200
        assert entry["method"] == "GET"

    def test_post_request(self, apache_log_lines) -> None:
        p = ApacheParser()
        entry = p.parse_line(apache_log_lines[1])
        assert entry is not None
        assert entry["method"] == "POST"
        assert entry["status"] == 201

    def test_unrecognised_line_returns_none(self) -> None:
        p = ApacheParser()
        # Apache parser returns None for lines that don't match its regex
        result = p.parse_line("not an apache log")
        assert result is None

    def test_parse_file(self, tmp_log_file, apache_log_lines) -> None:
        path = tmp_log_file(apache_log_lines)
        p = ApacheParser()
        entries = list(p.parse_file(str(path)))
        assert len(entries) == 3
        statuses = {e["status"] for e in entries}
        assert {200, 201, 404} == statuses


# ---------------------------------------------------------------------------
# SyslogParser
# ---------------------------------------------------------------------------

class TestSyslogParser:
    def test_valid_syslog_line(self, syslog_lines) -> None:
        p = SyslogParser()
        entry = p.parse_line(syslog_lines[0])
        assert entry is not None
        # syslog parser uses 'tag' for the program name
        assert "sshd" in entry.get("tag", "") or "sshd" in entry.get("message", "")

    def test_unrecognised_returns_raw(self) -> None:
        p = SyslogParser()
        # Syslog parser falls back to raw dict rather than returning None
        result = p.parse_line("totally different format")
        assert result is not None
        assert result.get("raw") is True

    def test_parse_file(self, tmp_log_file, syslog_lines) -> None:
        path = tmp_log_file(syslog_lines)
        p = SyslogParser()
        entries = list(p.parse_file(str(path)))
        assert len(entries) == 3


# ---------------------------------------------------------------------------
# AutoDetectParser
# ---------------------------------------------------------------------------

class TestAutoDetectParser:
    def test_auto_detects_json(self, json_log_lines) -> None:
        p = AutoDetectParser()
        entry = p.parse_line(json_log_lines[0])
        assert entry is not None
        assert entry["level"] == "INFO"

    def test_auto_detects_apache(self, apache_log_lines) -> None:
        p = AutoDetectParser()
        entry = p.parse_line(apache_log_lines[0])
        assert entry is not None
        assert entry.get("status") == 200

    def test_auto_detects_syslog(self, syslog_lines) -> None:
        p = AutoDetectParser()
        entry = p.parse_line(syslog_lines[0])
        assert entry is not None

    def test_raw_fallback(self) -> None:
        p = AutoDetectParser()
        entry = p.parse_line("some random text")
        assert entry is not None
        assert entry.get("raw") is True

    def test_empty_line_returns_none(self) -> None:
        p = AutoDetectParser()
        assert p.parse_line("") is None

    def test_parse_file_json(self, tmp_log_file, json_log_lines) -> None:
        path = tmp_log_file(json_log_lines)
        p = AutoDetectParser()
        entries = list(p.parse_file(str(path)))
        assert len(entries) == 4

    def test_parse_file_apache(self, tmp_log_file, apache_log_lines) -> None:
        path = tmp_log_file(apache_log_lines)
        p = AutoDetectParser()
        entries = list(p.parse_file(str(path)))
        assert len(entries) == 3

    def test_parse_file_empty(self, tmp_log_file) -> None:
        path = tmp_log_file([])
        p = AutoDetectParser()
        assert list(p.parse_file(str(path))) == []
