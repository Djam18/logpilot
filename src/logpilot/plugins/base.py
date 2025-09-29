"""Plugin system Protocol definitions.

Third-party plugins implement one or more of these Protocols and register
themselves via the entry-points mechanism:

    [project.entry-points."logpilot.plugins"]
    my_parser = "my_package.parsers:MyParser"

The plugin registry discovers and validates plugins at import time.
"""
from __future__ import annotations

from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class ParserPlugin(Protocol):
    """Protocol for custom log format parsers."""

    @property
    def name(self) -> str:
        """Unique format name, e.g. 'nginx', 'graylog'."""
        ...

    def parse_line(self, line: str) -> dict[str, Any] | None:
        """Parse a single log line. Return None to skip."""
        ...

    def parse_file(self, path: str) -> Iterator[dict[str, Any]]:
        """Stream-parse an entire file."""
        ...


@runtime_checkable
class AggregatorPlugin(Protocol):
    """Protocol for custom aggregators."""

    @property
    def name(self) -> str: ...

    def add(self, entry: dict[str, Any]) -> None: ...

    def result(self) -> dict[str, Any]: ...


@runtime_checkable
class OutputPlugin(Protocol):
    """Protocol for custom output formatters."""

    @property
    def name(self) -> str: ...

    def render(self, entries: list[dict[str, Any]]) -> str: ...
