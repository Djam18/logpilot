"""Alert rules engine — evaluate conditions against log entry streams."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

Predicate = Callable[[dict[str, Any]], bool]


@dataclass
class AlertRule:
    """A named rule that fires when its predicate matches a log entry.

    Attributes:
        name:       Human-readable rule name shown in alert payloads.
        predicate:  Callable that returns True when the rule should fire.
        cooldown:   Minimum seconds between repeated alerts for the same rule.
                    Set to 0 to fire on every matching entry.
        channels:   Names of alert channels to notify (must be registered in
                    the engine before the rule can fire).
    """

    name: str
    predicate: Predicate
    cooldown: float = 60.0
    channels: list[str] = field(default_factory=list)
    _last_fired: float = field(default=0.0, init=False, repr=False)

    def matches(self, entry: dict[str, Any]) -> bool:
        return self.predicate(entry)


class RulesEngine:
    """Evaluate a list of AlertRules against incoming log entries.

    Usage::

        engine = RulesEngine()
        engine.register_channel("slack", SlackChannel(webhook_url))
        engine.add_rule(AlertRule(
            name="High error rate",
            predicate=lambda e: e.get("level") == "ERROR",
            cooldown=30,
            channels=["slack"],
        ))

        for entry in parser.parse_file("app.log"):
            engine.evaluate(entry)
    """

    def __init__(self) -> None:
        self._rules: list[AlertRule] = []
        self._channels: dict[str, "AlertChannel"] = {}

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def register_channel(self, name: str, channel: "AlertChannel") -> None:
        self._channels[name] = channel

    def evaluate(self, entry: dict[str, Any]) -> list[str]:
        """Test entry against all rules; notify channels that have cooled down.

        Returns the list of rule names that fired.
        """
        import time

        fired: list[str] = []
        now = time.monotonic()
        for rule in self._rules:
            if not rule.matches(entry):
                continue
            if now - rule._last_fired < rule.cooldown:
                continue
            rule._last_fired = now
            fired.append(rule.name)
            self._dispatch(rule, entry)
        return fired

    def _dispatch(self, rule: AlertRule, entry: dict[str, Any]) -> None:
        for ch_name in rule.channels:
            channel = self._channels.get(ch_name)
            if channel is not None:
                channel.send(rule.name, entry)

    @property
    def rules(self) -> list[AlertRule]:
        return list(self._rules)


class AlertChannel:
    """Base class / Protocol for alert notification channels."""

    def send(self, rule_name: str, entry: dict[str, Any]) -> None:
        raise NotImplementedError
