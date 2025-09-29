"""Example OutputPlugin: render log entries as CSV."""
from __future__ import annotations

import csv
import io
from typing import Any


class CsvOutput:
    """Render a list of log entries as a CSV string.

    This example plugin demonstrates how to implement the OutputPlugin
    Protocol for use with logpilot's plugin registry.

    Entry-point registration (in your package's pyproject.toml)::

        [project.entry-points."logpilot.plugins"]
        csv_output = "my_package.plugins:CsvOutput"
    """

    @property
    def name(self) -> str:
        return "csv"

    def render(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return ""
        fieldnames = list(entries[0].keys())
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(entries)
        return buf.getvalue()
