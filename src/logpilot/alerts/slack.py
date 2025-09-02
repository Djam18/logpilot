"""Slack webhook alert channel."""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from .rules import AlertChannel

logger = logging.getLogger(__name__)


class SlackChannel(AlertChannel):
    """Send alert notifications to a Slack incoming webhook.

    The webhook URL must be set via the LOGPILOT_SLACK_WEBHOOK environment
    variable or passed directly to the constructor.

    Example payload sent to Slack::

        {
            "text": ":rotating_light: *logpilot alert: High error rate*",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Rule:* High error rate\\n*Entry:* ..."
                    }
                }
            ]
        }
    """

    def __init__(self, webhook_url: str, timeout: float = 5.0) -> None:
        if not webhook_url:
            raise ValueError("Slack webhook URL must not be empty")
        self._url = webhook_url
        self._timeout = timeout

    def send(self, rule_name: str, entry: dict[str, Any]) -> None:
        """POST a Slack message for the given rule and log entry.

        Failures are logged as warnings — alert delivery is best-effort
        and should never crash the main log processing pipeline.
        """
        message = entry.get("message", str(entry))[:300]
        payload = {
            "text": f":rotating_light: *logpilot alert: {rule_name}*",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Rule:* {rule_name}\n"
                            f"*Level:* {entry.get('level', 'unknown')}\n"
                            f"*Message:* {message}"
                        ),
                    },
                }
            ],
        }
        self._post(payload)

    def _post(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status != 200:
                    logger.warning(
                        "Slack webhook returned non-200 status: %s", resp.status
                    )
        except OSError as exc:
            logger.warning("Failed to send Slack alert: %s", exc)
