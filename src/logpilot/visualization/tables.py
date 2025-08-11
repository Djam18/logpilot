"""Rich-powered table and bar chart rendering for log analysis results."""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table
from rich import box

_console = Console()


def print_entries_table(
    entries: list[dict[str, Any]],
    fields: list[str] | None = None,
    title: str = "Log Entries",
    max_rows: int = 100,
) -> None:
    """Render log entries as a Rich table.

    Args:
        entries:   List of parsed log-entry dicts.
        fields:    Columns to display. Defaults to all keys found in the
                   first entry.
        title:     Table title shown in the header.
        max_rows:  Hard cap — large streams are truncated with a notice.
    """
    if not entries:
        _console.print("[yellow]No entries to display.[/yellow]")
        return

    cols = fields or list(entries[0].keys())
    table = Table(title=title, box=box.ROUNDED, show_lines=False)
    for col in cols:
        table.add_column(col, overflow="fold", max_width=60)

    shown = entries[:max_rows]
    for entry in shown:
        table.add_row(*[str(entry.get(c, "")) for c in cols])

    _console.print(table)
    if len(entries) > max_rows:
        _console.print(
            f"[dim]... and {len(entries) - max_rows} more rows (use --limit to adjust)[/dim]"
        )


def print_counter_table(
    counts: list[tuple[str, int]],
    title: str = "Top values",
    value_col: str = "Value",
    count_col: str = "Count",
) -> None:
    """Render a Counter.top() result as a Rich table."""
    table = Table(title=title, box=box.SIMPLE_HEAVY)
    table.add_column("#", style="dim", width=4)
    table.add_column(value_col)
    table.add_column(count_col, justify="right", style="cyan")

    for rank, (value, count) in enumerate(counts, start=1):
        table.add_row(str(rank), value, str(count))

    _console.print(table)


def print_bar_chart(
    counts: list[tuple[str, int]],
    title: str = "Distribution",
    width: int = 40,
) -> None:
    """Print an ASCII bar chart using Rich markup.

    Each bar is scaled relative to the maximum value.

    Args:
        counts: List of (label, value) pairs, highest first.
        title:  Printed as a heading above the chart.
        width:  Maximum bar width in characters.
    """
    if not counts:
        _console.print("[yellow]No data for chart.[/yellow]")
        return

    max_val = max(v for _, v in counts) or 1
    max_label = max(len(k) for k, _ in counts)

    _console.print(f"\n[bold]{title}[/bold]")
    for label, value in counts:
        bar_len = int(value / max_val * width)
        bar = "█" * bar_len
        pct = value / max_val * 100
        _console.print(
            f"  {label:<{max_label}}  [green]{bar:<{width}}[/green]"
            f"  [cyan]{value:>6}[/cyan] [dim]({pct:.1f}%)[/dim]"
        )
    _console.print()


def print_percentiles_table(
    summary: dict[str, float],
    title: str = "Percentile Summary",
    field: str = "",
) -> None:
    """Render a Percentiles.summary() dict as a Rich table."""
    display_title = f"{title} — {field}" if field else title
    table = Table(title=display_title, box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right", style="cyan")

    order = ["min", "p50", "p90", "p95", "p99", "max", "mean", "count"]
    for key in order:
        if key in summary:
            table.add_row(key, f"{summary[key]:.2f}")

    _console.print(table)
