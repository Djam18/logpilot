"""Tests for alert rules engine, anomaly detector, and channels."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from logpilot.alerts.anomaly import AnomalyAlertPredicate, AnomalyDetector, AnomalyResult
from logpilot.alerts.rules import AlertChannel, AlertRule, RulesEngine
from logpilot.alerts.slack import SlackChannel


# ---------------------------------------------------------------------------
# AlertRule + RulesEngine
# ---------------------------------------------------------------------------

class TestAlertRule:
    def _error_entry(self) -> dict[str, Any]:
        return {"level": "ERROR", "message": "disk full"}

    def test_matches_predicate(self) -> None:
        rule = AlertRule(
            name="errors",
            predicate=lambda e: e.get("level") == "ERROR",
        )
        assert rule.matches(self._error_entry())
        assert not rule.matches({"level": "INFO", "message": "ok"})

    def test_repr_includes_name(self) -> None:
        rule = AlertRule(name="test-rule", predicate=lambda e: True)
        assert "test-rule" in repr(rule)


class TestRulesEngine:
    def _make_engine(self) -> tuple[RulesEngine, list[str]]:
        fired: list[str] = []

        class RecordingChannel(AlertChannel):
            def send(self, rule_name: str, entry: dict[str, Any]) -> None:
                fired.append(rule_name)

        engine = RulesEngine()
        engine.register_channel("rec", RecordingChannel())
        return engine, fired

    def test_fires_matching_rule(self) -> None:
        engine, fired = self._make_engine()
        engine.add_rule(AlertRule(
            name="errors",
            predicate=lambda e: e.get("level") == "ERROR",
            cooldown=0,
            channels=["rec"],
        ))
        result = engine.evaluate({"level": "ERROR", "message": "bad"})
        assert "errors" in result
        assert "errors" in fired

    def test_does_not_fire_non_matching(self) -> None:
        engine, fired = self._make_engine()
        engine.add_rule(AlertRule(
            name="errors",
            predicate=lambda e: e.get("level") == "ERROR",
            cooldown=0,
            channels=["rec"],
        ))
        engine.evaluate({"level": "INFO", "message": "ok"})
        assert fired == []

    def test_cooldown_suppresses_repeat_fires(self) -> None:
        engine, fired = self._make_engine()
        engine.add_rule(AlertRule(
            name="errors",
            predicate=lambda e: True,
            cooldown=60.0,
            channels=["rec"],
        ))
        engine.evaluate({"level": "ERROR"})
        engine.evaluate({"level": "ERROR"})
        assert len(fired) == 1  # second call suppressed by cooldown

    def test_cooldown_zero_fires_every_time(self) -> None:
        engine, fired = self._make_engine()
        engine.add_rule(AlertRule(
            name="errors",
            predicate=lambda e: True,
            cooldown=0,
            channels=["rec"],
        ))
        engine.evaluate({"level": "ERROR"})
        engine.evaluate({"level": "ERROR"})
        assert len(fired) == 2

    def test_unknown_channel_silently_skipped(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AlertRule(
            name="test",
            predicate=lambda e: True,
            cooldown=0,
            channels=["nonexistent"],
        ))
        # Should not raise
        engine.evaluate({"message": "ok"})

    def test_rules_property(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AlertRule(name="a", predicate=lambda e: True))
        engine.add_rule(AlertRule(name="b", predicate=lambda e: True))
        assert len(engine.rules) == 2


# ---------------------------------------------------------------------------
# SlackChannel
# ---------------------------------------------------------------------------

class TestSlackChannel:
    def test_empty_url_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            SlackChannel("")

    def test_send_posts_to_webhook(self) -> None:
        channel = SlackChannel("https://hooks.slack.com/test")
        with patch.object(channel, "_post") as mock_post:
            channel.send("High errors", {"level": "ERROR", "message": "disk full"})
        mock_post.assert_called_once()
        payload = mock_post.call_args[0][0]
        assert "High errors" in payload["text"]
        assert any("High errors" in str(b) for b in payload["blocks"])

    def test_network_error_does_not_raise(self) -> None:
        channel = SlackChannel("https://hooks.slack.com/test")
        with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            # Should log warning but not raise
            channel.send("test", {"level": "ERROR", "message": "bad"})


# ---------------------------------------------------------------------------
# AnomalyDetector
# ---------------------------------------------------------------------------

class TestAnomalyDetector:
    def _warm_up(self, detector: AnomalyDetector, n: int = 30, base: float = 100.0) -> None:
        for i in range(n):
            detector.update({"latency": base + (i % 5)})

    def test_no_anomaly_during_warmup(self) -> None:
        d = AnomalyDetector(field="latency", threshold=3.0, min_samples=30)
        for _ in range(29):
            result = d.update({"latency": 9999.0})  # huge value
            assert not result.is_anomaly

    def test_detects_anomaly_after_warmup(self) -> None:
        d = AnomalyDetector(field="latency", threshold=3.0, min_samples=10)
        # Use varied values so std > 0 (required for z-score computation)
        for i in range(10):
            d.update({"latency": 100.0 + (i % 3)})
        # A wildly different value should trigger
        result = d.update({"latency": 9999.0})
        assert result.is_anomaly
        assert result.z_score is not None

    def test_skips_missing_field(self) -> None:
        d = AnomalyDetector(field="latency")
        result = d.update({"message": "no latency"})
        assert result.skipped
        assert result.z_score is None

    def test_skips_non_numeric(self) -> None:
        d = AnomalyDetector(field="latency")
        result = d.update({"latency": "fast"})
        assert result.skipped

    def test_count_increments(self) -> None:
        d = AnomalyDetector(field="latency")
        for i in range(5):
            d.update({"latency": float(i)})
        assert d.count == 5

    def test_mean_converges(self) -> None:
        d = AnomalyDetector(field="latency", min_samples=0)
        for _ in range(100):
            d.update({"latency": 10.0})
        assert abs(d.mean - 10.0) < 0.01

    def test_reset_clears_state(self) -> None:
        d = AnomalyDetector(field="latency")
        d.update({"latency": 100.0})
        d.reset()
        assert d.count == 0
        assert d.mean == 0.0


class TestAnomalyAlertPredicate:
    def test_integrates_with_rules_engine(self) -> None:
        detector = AnomalyDetector(field="latency", threshold=3.0, min_samples=5)
        predicate = AnomalyAlertPredicate(detector)
        fired: list[bool] = []

        engine = RulesEngine()

        class FiredChannel(AlertChannel):
            def send(self, rule_name: str, entry: dict[str, Any]) -> None:
                fired.append(True)

        engine.register_channel("test", FiredChannel())
        engine.add_rule(AlertRule(
            name="latency anomaly",
            predicate=predicate,
            cooldown=0,
            channels=["test"],
        ))

        # Warm up with varied values so std > 0
        for i in range(5):
            engine.evaluate({"latency": 100.0 + (i % 3)})

        # Inject anomaly
        engine.evaluate({"latency": 99999.0})
        assert len(fired) >= 1
