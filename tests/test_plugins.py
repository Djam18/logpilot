"""Tests for the plugin system."""
from __future__ import annotations

from typing import Any, Iterator

import pytest

from logpilot.plugins.base import AggregatorPlugin, OutputPlugin, ParserPlugin
from logpilot.plugins.examples.csv_output import CsvOutput
from logpilot.plugins.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Minimal plugin implementations for testing
# ---------------------------------------------------------------------------

class _GoodParser:
    @property
    def name(self) -> str:
        return "test-parser"

    def parse_line(self, line: str) -> dict[str, Any] | None:
        return {"message": line} if line else None

    def parse_file(self, path: str) -> Iterator[dict[str, Any]]:
        with open(path) as f:
            for line in f:
                entry = self.parse_line(line.strip())
                if entry:
                    yield entry


class _GoodAggregator:
    @property
    def name(self) -> str:
        return "test-agg"

    def add(self, entry: dict[str, Any]) -> None:
        pass

    def result(self) -> dict[str, Any]:
        return {}


class _GoodOutput:
    @property
    def name(self) -> str:
        return "test-output"

    def render(self, entries: list[dict[str, Any]]) -> str:
        return str(entries)


# ---------------------------------------------------------------------------
# Protocol checks
# ---------------------------------------------------------------------------

class TestProtocols:
    def test_parser_protocol(self) -> None:
        assert isinstance(_GoodParser(), ParserPlugin)

    def test_aggregator_protocol(self) -> None:
        assert isinstance(_GoodAggregator(), AggregatorPlugin)

    def test_output_protocol(self) -> None:
        assert isinstance(_GoodOutput(), OutputPlugin)

    def test_bad_parser_not_instance(self) -> None:
        class BadParser:
            pass
        assert not isinstance(BadParser(), ParserPlugin)


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    def _registry(self) -> PluginRegistry:
        return PluginRegistry()

    def test_register_and_get_parser(self) -> None:
        r = self._registry()
        r.register_parser(_GoodParser())
        assert r.get_parser("test-parser") is not None

    def test_register_and_get_aggregator(self) -> None:
        r = self._registry()
        r.register_aggregator(_GoodAggregator())
        assert r.get_aggregator("test-agg") is not None

    def test_register_and_get_output(self) -> None:
        r = self._registry()
        r.register_output(_GoodOutput())
        assert r.get_output("test-output") is not None

    def test_get_missing_returns_none(self) -> None:
        r = self._registry()
        assert r.get_parser("nonexistent") is None

    def test_register_bad_parser_raises(self) -> None:
        r = self._registry()
        with pytest.raises(TypeError):
            r.register_parser(object())  # type: ignore[arg-type]

    def test_list_parsers_sorted(self) -> None:
        r = self._registry()

        class BParser:
            name = "b"
            def parse_line(self, line: str) -> dict[str, Any] | None: return None
            def parse_file(self, path: str) -> Iterator[dict[str, Any]]: return iter([])

        class AParser:
            name = "a"
            def parse_line(self, line: str) -> dict[str, Any] | None: return None
            def parse_file(self, path: str) -> Iterator[dict[str, Any]]: return iter([])

        r.register_parser(BParser())
        r.register_parser(AParser())
        assert r.list_parsers() == ["a", "b"]

    def test_discover_returns_zero_without_entrypoints(self) -> None:
        r = self._registry()
        # In the test environment there are no logpilot.plugins entry-points
        count = r.discover()
        assert count == 0


# ---------------------------------------------------------------------------
# CsvOutput example plugin
# ---------------------------------------------------------------------------

class TestCsvOutput:
    def test_name(self) -> None:
        assert CsvOutput().name == "csv"

    def test_implements_protocol(self) -> None:
        assert isinstance(CsvOutput(), OutputPlugin)

    def test_render_empty(self) -> None:
        assert CsvOutput().render([]) == ""

    def test_render_entries(self) -> None:
        entries = [
            {"level": "INFO", "message": "startup"},
            {"level": "ERROR", "message": "crash"},
        ]
        csv_str = CsvOutput().render(entries)
        assert "level" in csv_str
        assert "INFO" in csv_str
        assert "ERROR" in csv_str
        lines = csv_str.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows
