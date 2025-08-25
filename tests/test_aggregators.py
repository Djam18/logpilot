"""Tests for aggregator modules."""
from __future__ import annotations

import pytest

from logpilot.aggregators.counter import Counter
from logpilot.aggregators.groupby import GroupBy
from logpilot.aggregators.percentiles import Percentiles, _percentile


# ---------------------------------------------------------------------------
# Counter
# ---------------------------------------------------------------------------

class TestCounter:
    def test_counts_field_values(self) -> None:
        c = Counter("level")
        c.add({"level": "ERROR"})
        c.add({"level": "INFO"})
        c.add({"level": "ERROR"})
        top = c.top(10)
        assert top[0] == ("ERROR", 2)
        assert top[1] == ("INFO", 1)

    def test_missing_field_counts_as_unknown(self) -> None:
        c = Counter("level")
        c.add({"message": "no level here"})
        assert c.top(1)[0][0] == "unknown"

    def test_total(self) -> None:
        c = Counter("level")
        for _ in range(5):
            c.add({"level": "INFO"})
        assert c.total == 5

    def test_top_n_limit(self) -> None:
        c = Counter("level")
        for lvl in ["A", "B", "C", "D", "E"]:
            c.add({"level": lvl})
        assert len(c.top(3)) == 3


# ---------------------------------------------------------------------------
# GroupBy
# ---------------------------------------------------------------------------

class TestGroupBy:
    def _sample(self) -> list[dict]:
        return [
            {"level": "ERROR", "message": "e1"},
            {"level": "INFO", "message": "i1"},
            {"level": "ERROR", "message": "e2"},
            {"level": "WARN", "message": "w1"},
        ]

    def test_groups_correctly(self) -> None:
        gb = GroupBy("level")
        for e in self._sample():
            gb.add(e)
        assert len(gb.get("ERROR")) == 2
        assert len(gb.get("INFO")) == 1

    def test_keys_sorted(self) -> None:
        gb = GroupBy("level")
        for e in self._sample():
            gb.add(e)
        assert gb.keys() == sorted(["ERROR", "INFO", "WARN"])

    def test_counts(self) -> None:
        gb = GroupBy("level")
        for e in self._sample():
            gb.add(e)
        counts = gb.counts()
        assert counts["ERROR"] == 2

    def test_len(self) -> None:
        gb = GroupBy("level")
        for e in self._sample():
            gb.add(e)
        assert len(gb) == 3

    def test_missing_field_bucketed_as_unknown(self) -> None:
        gb = GroupBy("level")
        gb.add({"message": "no level"})
        assert "unknown" in gb.keys()

    def test_get_missing_key_returns_empty(self) -> None:
        gb = GroupBy("level")
        assert gb.get("NONEXISTENT") == []


# ---------------------------------------------------------------------------
# Percentiles
# ---------------------------------------------------------------------------

class TestPercentileHelper:
    def test_single_value(self) -> None:
        assert _percentile([42.0], 50) == 42.0

    def test_empty_returns_zero(self) -> None:
        assert _percentile([], 99) == 0.0

    def test_p50_of_even_list(self) -> None:
        vals = sorted([float(x) for x in range(1, 101)])
        result = _percentile(vals, 50)
        assert 49.0 <= result <= 51.0


class TestPercentiles:
    def _load(self, values: list[float]) -> Percentiles:
        p = Percentiles("latency")
        for v in values:
            p.add({"latency": v})
        return p

    def test_summary_keys(self) -> None:
        p = self._load([float(x) for x in range(1, 101)])
        s = p.summary()
        assert all(k in s for k in ["p50", "p90", "p95", "p99", "min", "max", "mean", "count"])

    def test_min_max(self) -> None:
        p = self._load([1.0, 5.0, 10.0])
        s = p.summary()
        assert s["min"] == 1.0
        assert s["max"] == 10.0

    def test_count(self) -> None:
        p = self._load([1.0, 2.0, 3.0])
        assert len(p) == 3

    def test_non_numeric_ignored(self) -> None:
        p = Percentiles("latency")
        p.add({"latency": "not-a-number"})
        p.add({"latency": 5.0})
        assert len(p) == 1

    def test_missing_field_ignored(self) -> None:
        p = Percentiles("latency")
        p.add({"message": "no latency here"})
        assert len(p) == 0

    def test_custom_percentile_list(self) -> None:
        p = self._load([float(x) for x in range(1, 101)])
        s = p.summary(percentiles=[25, 75])
        assert "p25" in s
        assert "p75" in s
        assert "p50" not in s
