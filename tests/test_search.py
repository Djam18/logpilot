"""Tests for search and filter modules."""
from __future__ import annotations

from datetime import datetime

import pytest

from logpilot.search.filter_chain import AnyFilter, FilterChain
from logpilot.search.regex_search import RegexSearch
from logpilot.search.time_filter import TimeRangeFilter, _parse_timestamp


# ---------------------------------------------------------------------------
# RegexSearch
# ---------------------------------------------------------------------------

class TestRegexSearch:
    def test_matches_value(self) -> None:
        s = RegexSearch("error")
        assert s.matches({"message": "disk error occurred"})

    def test_no_match(self) -> None:
        s = RegexSearch("error")
        assert not s.matches({"message": "everything is fine"})

    def test_case_insensitive_by_default(self) -> None:
        s = RegexSearch("ERROR")
        assert s.matches({"message": "disk error"})

    def test_field_targeting(self) -> None:
        s = RegexSearch("error", fields=["message"])
        assert s.matches({"message": "disk error", "level": "INFO"})
        assert not s.matches({"message": "ok", "level": "error"})

    def test_filter_returns_subset(self) -> None:
        entries = [
            {"message": "disk error"},
            {"message": "all good"},
            {"message": "another error"},
        ]
        result = RegexSearch("error").filter(entries)
        assert len(result) == 2

    def test_empty_entries(self) -> None:
        assert RegexSearch("x").filter([]) == []


# ---------------------------------------------------------------------------
# TimeRangeFilter
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    @pytest.mark.parametrize("raw", [
        "2025-08-01T10:00:00",
        "2025-08-01T10:00:00Z",
        "2025-08-01 10:00:00",
        "2025-08-01",
    ])
    def test_iso_formats(self, raw: str) -> None:
        result = _parse_timestamp(raw)
        assert result is not None
        assert result.year == 2025

    def test_returns_none_for_garbage(self) -> None:
        assert _parse_timestamp("not a date") is None


class TestTimeRangeFilter:
    def _make_entries(self) -> list[dict]:
        return [
            {"timestamp": "2025-08-01T09:00:00", "message": "early"},
            {"timestamp": "2025-08-01T10:00:00", "message": "start"},
            {"timestamp": "2025-08-01T11:00:00", "message": "middle"},
            {"timestamp": "2025-08-01T12:00:00", "message": "end"},
        ]

    def test_start_only(self) -> None:
        f = TimeRangeFilter(start=datetime(2025, 8, 1, 10))
        result = list(f.filter(iter(self._make_entries())))
        assert len(result) == 3

    def test_end_only(self) -> None:
        f = TimeRangeFilter(end=datetime(2025, 8, 1, 11))
        result = list(f.filter(iter(self._make_entries())))
        assert len(result) == 3

    def test_start_and_end(self) -> None:
        f = TimeRangeFilter(
            start=datetime(2025, 8, 1, 10),
            end=datetime(2025, 8, 1, 11),
        )
        result = list(f.filter(iter(self._make_entries())))
        assert len(result) == 2

    def test_no_timestamp_field(self) -> None:
        f = TimeRangeFilter(start=datetime(2025, 1, 1))
        assert not f.matches({"message": "no timestamp"})

    def test_unparseable_timestamp(self) -> None:
        f = TimeRangeFilter(start=datetime(2025, 1, 1))
        assert not f.matches({"timestamp": "not-a-date"})


# ---------------------------------------------------------------------------
# FilterChain
# ---------------------------------------------------------------------------

class TestFilterChain:
    def _entries(self) -> list[dict]:
        return [
            {"message": "disk error", "level": "ERROR", "timestamp": "2025-08-01T10:00:00"},
            {"message": "all good", "level": "INFO", "timestamp": "2025-08-01T10:01:00"},
            {"message": "network error", "level": "ERROR", "timestamp": "2025-08-01T10:02:00"},
            {"message": "cache warn", "level": "WARN", "timestamp": "2025-08-01T10:03:00"},
        ]

    def test_single_predicate(self) -> None:
        chain = FilterChain().add(RegexSearch("error").matches)
        result = list(chain.apply(iter(self._entries())))
        assert len(result) == 2

    def test_two_predicates_and(self) -> None:
        chain = (
            FilterChain()
            .add(RegexSearch("error").matches)
            .add(lambda e: e.get("level") == "ERROR")
        )
        result = list(chain.apply(iter(self._entries())))
        assert len(result) == 2

    def test_combine_with_and_operator(self) -> None:
        a = FilterChain().add(RegexSearch("error").matches)
        b = FilterChain().add(lambda e: "disk" in e.get("message", ""))
        combined = a & b
        result = list(combined.apply(iter(self._entries())))
        assert len(result) == 1

    def test_empty_chain_passes_all(self) -> None:
        chain = FilterChain()
        result = list(chain.apply(iter(self._entries())))
        assert len(result) == 4

    def test_len(self) -> None:
        chain = FilterChain().add(lambda e: True).add(lambda e: False)
        assert len(chain) == 2

    def test_repr(self) -> None:
        assert "2 predicates" in repr(FilterChain().add(lambda e: True).add(lambda e: True))


class TestAnyFilter:
    def test_or_semantics(self) -> None:
        f = AnyFilter(
            lambda e: e.get("level") == "ERROR",
            lambda e: e.get("level") == "WARN",
        )
        entries = [
            {"level": "ERROR", "message": "bad"},
            {"level": "INFO", "message": "fine"},
            {"level": "WARN", "message": "watch out"},
        ]
        result = list(f.apply(iter(entries)))
        assert len(result) == 2

    def test_no_match(self) -> None:
        f = AnyFilter(lambda e: False, lambda e: False)
        assert not f.matches({"level": "INFO"})
