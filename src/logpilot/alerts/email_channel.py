"""Email alert channel via SMTP."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .rules import AlertChannel

logger = logging.getLogger(__name__)


class EmailChannel(AlertChannel):
    """Send alert notifications via SMTP.

    Configuration is read from environment variables when not passed
    explicitly to the constructor:

        LOGPILOT_SMTP_HOST     (default: localhost)
        LOGPILOT_SMTP_PORT     (default: 587)
        LOGPILOT_SMTP_USER
        LOGPILOT_SMTP_PASSWORD
        LOGPILOT_SMTP_FROM
        LOGPILOT_SMTP_TO       comma-separated list

    Example::

        channel = EmailChannel(
            host="smtp.gmail.com",
            port=587,
            username="bot@example.com",
            password="...",
            from_addr="alerts@example.com",
            to_addrs=["ops@example.com", "oncall@example.com"],
        )
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "logpilot@localhost",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_addr
        self._to = to_addrs or []
        self._use_tls = use_tls
        self._timeout = timeout

        if not self._to:
            raise ValueError("EmailChannel requires at least one recipient address")

    def send(self, rule_name: str, entry: dict[str, Any]) -> None:
        """Send an email alert for the triggered rule.

        Failures are logged as warnings and never propagate to the caller.
        """
        subject = f"[logpilot] Alert: {rule_name}"
        body = self._build_body(rule_name, entry)
        try:
            self._send_smtp(subject, body)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("Failed to send email alert: %s", exc)

    def _build_body(self, rule_name: str, entry: dict[str, Any]) -> str:
        lines = [
            f"logpilot Alert — {rule_name}",
            "=" * 40,
            f"Rule   : {rule_name}",
            f"Level  : {entry.get('level', 'unknown')}",
            f"Message: {entry.get('message', str(entry))[:500]}",
            "",
            "Full entry:",
        ]
        for k, v in entry.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def _send_smtp(self, subject: str, body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = ", ".join(self._to)
        msg.attach(MIMEText(body, "plain"))

        smtp_cls = smtplib.SMTP
        with smtp_cls(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.sendmail(self._from, self._to, msg.as_string())
            logger.debug("Email alert sent to %s", self._to)
