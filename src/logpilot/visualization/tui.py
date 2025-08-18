"""Textual TUI dashboard for real-time log tailing.

Launch with:
    logpilot tail --tui /var/log/app.log
    python -c "from logpilot.visualization.tui import run_dashboard; run_dashboard('app.log')"

Requires: textual>=0.47
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
)

from ..parsers.auto_detect import AutoDetectParser, detect_format


class StatsBar(Static):
    """Status bar showing live entry count and detected format."""

    count: reactive[int] = reactive(0)
    fmt: reactive[str] = reactive("auto")
    errors: reactive[int] = reactive(0)

    def render(self) -> str:
        return (
            f"[bold cyan]Entries:[/bold cyan] {self.count}  "
            f"[bold cyan]Format:[/bold cyan] {self.fmt}  "
            f"[bold red]Errors:[/bold red] {self.errors}"
        )


class LiveLogView(RichLog):
    """Scrollable log view that auto-scrolls on new lines."""

    BORDER_TITLE = "Live Log"

    def on_mount(self) -> None:
        self.auto_scroll = True


class TopFieldsTable(DataTable):
    """Mini table showing the top 5 values for a field."""

    BORDER_TITLE = "Top Values"

    def on_mount(self) -> None:
        self.add_columns("Value", "Count")
        self.cursor_type = "none"

    def update_counts(self, counts: list[tuple[str, int]]) -> None:
        self.clear()
        for value, count in counts[:5]:
            self.add_row(value[:40], str(count))


class LogDashboard(App[None]):
    """Full-screen TUI dashboard with live log tailing.

    Keybindings:
        q / ctrl+c  — quit
        p           — pause / resume tailing
        c           — clear log view
        f           — toggle format display
    """

    CSS = """
    Screen {
        layout: vertical;
    }
    Horizontal {
        height: 12;
    }
    LiveLogView {
        border: round $primary;
        height: 1fr;
    }
    TopFieldsTable {
        border: round $secondary;
        width: 40;
    }
    StatsBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("c", "clear_log", "Clear"),
    ]

    def __init__(self, log_path: str, poll_interval: float = 0.25) -> None:
        super().__init__()
        self._path = Path(log_path)
        self._poll_interval = poll_interval
        self._paused = False
        self._parser = AutoDetectParser()
        self._counts: dict[str, int] = {}
        self._error_count = 0
        self._file_offset = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield LiveLogView(id="log_view", max_lines=500, markup=True)
            with Vertical():
                yield Label("[bold]Field: level[/bold]", id="field_label")
                yield TopFieldsTable(id="top_table")
        yield StatsBar(id="stats_bar")
        yield Footer()

    def on_mount(self) -> None:
        # Seek to end of file on startup — only tail new lines
        if self._path.exists():
            self._file_offset = self._path.stat().st_size
        self.set_interval(self._poll_interval, self._poll_file)

    def _poll_file(self) -> None:
        if self._paused or not self._path.exists():
            return
        try:
            with self._path.open(encoding="utf-8", errors="replace") as fh:
                fh.seek(self._file_offset)
                new_data = fh.read()
                self._file_offset = fh.tell()
        except OSError:
            return

        if not new_data:
            return

        log_view = self.query_one("#log_view", LiveLogView)
        stats = self.query_one("#stats_bar", StatsBar)
        top_table = self.query_one("#top_table", TopFieldsTable)

        for raw_line in new_data.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            entry = self._parser.parse_line(raw_line)
            if entry is None:
                self._error_count += 1
                continue

            # Detect format on first real line
            if stats.fmt == "auto":
                stats.fmt = detect_format(raw_line)

            # Colour-code by level if present
            level = str(entry.get("level", entry.get("severity", ""))).upper()
            colour = {
                "ERROR": "red", "CRITICAL": "bold red",
                "WARN": "yellow", "WARNING": "yellow",
                "INFO": "green", "DEBUG": "dim",
            }.get(level, "white")

            display = entry.get("message", raw_line)[:200]
            log_view.write(f"[{colour}]{display}[/{colour}]")

            # Track level counts for the sidebar
            if level:
                self._counts[level] = self._counts.get(level, 0) + 1

            stats.count += 1
            stats.errors = self._error_count

        # Refresh top-values table
        sorted_counts = sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        top_table.update_counts(sorted_counts)

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        status = "[yellow]PAUSED[/yellow]" if self._paused else "[green]LIVE[/green]"
        self.query_one("#log_view", LiveLogView).write(f"--- {status} ---")

    def action_clear_log(self) -> None:
        self.query_one("#log_view", LiveLogView).clear()


def run_dashboard(log_path: str, poll_interval: float = 0.25) -> None:
    """Entry point for the TUI dashboard."""
    app = LogDashboard(log_path=log_path, poll_interval=poll_interval)
    app.run()
