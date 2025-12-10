"""Logpilot CLI — entry point.

Commands:
    logpilot parse   <file>           Parse and display log entries
    logpilot search  <file> <pattern> Regex search across entries
    logpilot stats   <file>           Aggregate statistics
    logpilot tail    <file>           Live tail (coloured stream or TUI)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.table import Table

from .parsers.auto_detect import AutoDetectParser

console = Console()
err_console = Console(stderr=True)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _level_colour(level: str) -> str:
    return {
        "ERROR": "red",
        "CRITICAL": "bold red",
        "WARN": "yellow",
        "WARNING": "yellow",
        "DEBUG": "dim",
        "INFO": "green",
    }.get(level.upper(), "white")


def _entry_columns(entry: dict[str, Any]) -> tuple[str, str, str]:
    """Return (timestamp, level, message) strings for any log format."""
    ts = str(
        entry.get("timestamp")
        or entry.get("time")
        or entry.get("@timestamp")
        or ""
    )
    level = str(
        entry.get("level")
        or entry.get("severity")
        or entry.get("lvl")
        or "INFO"
    ).upper()

    # Apache: show method + path + status
    if "method" in entry and "path" in entry and "status" in entry:
        msg = f"{entry['method']} {entry['path']} → {entry['status']} ({entry.get('bytes', '-')} B)"
    # Syslog: show tag + message
    elif "tag" in entry and "hostname" in entry:
        msg = f"[{entry['tag']}] {entry.get('message', '')}"
    else:
        msg = str(
            entry.get("message")
            or entry.get("msg")
            or entry.get("body")
            or ""
        )

    return ts, level, msg


# ── CLI root ─────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version="1.0.0", prog_name="logpilot")
def main() -> None:
    """logpilot — fast, extensible log analysis CLI."""


# ── parse ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format", "-f", "fmt", default="auto",
    type=click.Choice(["auto", "json", "apache", "syslog"], case_sensitive=False),
    help="Input format (default: auto-detect).",
    show_default=True,
)
@click.option(
    "--output", "-o", "output_fmt", default="table",
    type=click.Choice(["table", "stream", "json"], case_sensitive=False),
    help="Output format.",
    show_default=True,
)
@click.option("--limit", "-n", default=0, type=int, help="Max entries to display (0 = all).")
@click.option("--fields", default="", help="Comma-separated fields to include in table output.")
@click.option("--workers", "-w", default=1, type=int, help="Parallel workers (0 = auto, requires large files).")
def parse(
    file: Path,
    fmt: str,
    output_fmt: str,
    limit: int,
    fields: str,
    workers: int,
) -> None:
    """Parse a log file and display entries.

    Auto-detects format from content (JSON, Apache, syslog, raw).

    \b
    Examples:
      logpilot parse app.json
      logpilot parse access.log --format apache --output table
      logpilot parse app.json --output json --limit 100
      logpilot parse huge.log --workers 0
    """
    # Parallel mode for large files
    if workers != 1:
        from .perf.parallel_parser import parse_file_parallel
        n = workers if workers > 0 else None
        entries_list = parse_file_parallel(str(file), workers=n)
        entries_iter = iter(entries_list)
    else:
        parser = AutoDetectParser(hint=fmt)
        entries_iter = parser.parse_file(str(file))

    selected_fields = [f.strip() for f in fields.split(",") if f.strip()]

    if output_fmt == "json":
        count = 0
        for entry in entries_iter:
            if limit and count >= limit:
                break
            out = {k: entry[k] for k in selected_fields if k in entry} if selected_fields else entry
            click.echo(json.dumps(out, default=str))
            count += 1
        err_console.print(f"[dim]Parsed {count} entries from {file}[/dim]")
        return

    if output_fmt == "table":
        collected: list[dict[str, Any]] = []
        for entry in entries_iter:
            if limit and len(collected) >= limit:
                break
            collected.append(entry)

        if not collected:
            err_console.print("[yellow]No entries found.[/yellow]")
            return

        # Use smart default columns for known formats
        first = collected[0]
        if not selected_fields:
            if "method" in first and "path" in first and "status" in first:
                # Apache access log: skip None-heavy fields
                cols = [k for k in first if first[k] is not None and k not in ("referrer", "user_agent", "protocol")]
            else:
                cols = list(first.keys())
        else:
            cols = selected_fields
        tbl = Table(
            title=f"{file.name}",
            box=box.ROUNDED,
            show_lines=False,
            highlight=True,
        )
        for col in cols:
            tbl.add_column(col, overflow="fold", max_width=70)

        for entry in collected:
            # Colour entire row by level
            level_val = str(entry.get("level") or entry.get("severity") or "").upper()
            style = {"ERROR": "red", "WARN": "yellow", "WARNING": "yellow", "CRITICAL": "bold red"}.get(level_val, "")
            tbl.add_row(*[str(entry.get(c, "")) for c in cols], style=style)

        console.print(tbl)
        if limit and len(collected) == limit:
            console.print(f"[dim]Showing first {limit} entries. Use --limit 0 to see all.[/dim]")
        else:
            console.print(f"[dim]{len(collected)} entries from {file.name}[/dim]")
        return

    # stream (default coloured output)
    count = 0
    for entry in entries_iter:
        if limit and count >= limit:
            break
        ts, level, msg = _entry_columns(entry)
        colour = _level_colour(level)
        console.print(
            f"[dim]{ts}[/dim] [{colour}]{level:8}[/{colour}] {msg}"
        )
        count += 1

    console.print(f"\n[dim]Parsed {count} entries from {file.name}[/dim]")


# ── search ───────────────────────────────────────────────────────────────────


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.argument("pattern")
@click.option(
    "--format", "-f", "fmt", default="auto",
    type=click.Choice(["auto", "json", "apache", "syslog"], case_sensitive=False),
    help="Input format.",
)
@click.option("--field", default="", help="Restrict match to a specific field (e.g. message).")
@click.option("--case-sensitive", is_flag=True, help="Case-sensitive matching (default: insensitive).")
@click.option("--since", default="", help="Start time filter (ISO-8601, e.g. 2025-12-01T10:00:00).")
@click.option("--until", default="", help="End time filter (ISO-8601).")
@click.option(
    "--output", "-o", "output_fmt", default="stream",
    type=click.Choice(["stream", "json", "table"], case_sensitive=False),
    help="Output format.",
    show_default=True,
)
@click.option("--limit", "-n", default=0, type=int, help="Max results to display (0 = all).")
def search(
    file: Path,
    pattern: str,
    fmt: str,
    field: str,
    case_sensitive: bool,
    since: str,
    until: str,
    output_fmt: str,
    limit: int,
) -> None:
    """Search log entries matching a regex pattern.

    \b
    Examples:
      logpilot search app.json "disk full"
      logpilot search app.json "ERROR" --field level
      logpilot search access.log "404" --field status --output table
      logpilot search app.json "timeout" --since 2025-12-01T10:00:00
    """
    from .search.regex_search import RegexSearch
    from .search.filter_chain import FilterChain

    flags = 0 if case_sensitive else re.IGNORECASE
    fields_list = [field] if field else None
    searcher = RegexSearch(pattern=pattern, flags=flags, fields=fields_list)
    chain = FilterChain().add(searcher.matches)

    # Time-range filter
    if since or until:
        from .search.time_filter import TimeRangeFilter
        from datetime import datetime

        def _parse_dt(s: str) -> datetime:
            for fmt_str in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s, fmt_str)
                except ValueError:
                    pass
            raise click.BadParameter(f"Cannot parse date: {s!r}. Use ISO-8601 format.")

        start_dt = _parse_dt(since) if since else None
        end_dt = _parse_dt(until) if until else None
        time_filter = TimeRangeFilter(start=start_dt, end=end_dt)
        chain = chain.add(time_filter.matches)

    parser = AutoDetectParser(hint=fmt)
    results: list[dict[str, Any]] = []

    for entry in parser.parse_file(str(file)):
        if chain.matches(entry):
            results.append(entry)
            if limit and len(results) >= limit:
                break

    if not results:
        err_console.print(f"[yellow]No matches for pattern {pattern!r}[/yellow]")
        return

    if output_fmt == "json":
        for entry in results:
            click.echo(json.dumps(entry, default=str))
    elif output_fmt == "table":
        cols = list(results[0].keys())
        tbl = Table(
            title=f"Search results: {pattern!r} in {file.name}",
            box=box.ROUNDED,
        )
        for col in cols:
            tbl.add_column(col, overflow="fold", max_width=60)
        for entry in results:
            level_val = str(entry.get("level") or "").upper()
            style = {"ERROR": "red", "WARN": "yellow", "WARNING": "yellow"}.get(level_val, "")
            tbl.add_row(*[str(entry.get(c, "")) for c in cols], style=style)
        console.print(tbl)
    else:
        for entry in results:
            ts, level, msg = _entry_columns(entry)
            colour = _level_colour(level)
            console.print(f"[dim]{ts}[/dim] [{colour}]{level:8}[/{colour}] {msg}")

    console.print(f"\n[dim]{len(results)} match{'es' if len(results) != 1 else ''} for {pattern!r} in {file.name}[/dim]")


# ── stats ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--by", "-b", default="level", help="Field to count/group by.", show_default=True)
@click.option("--top", "-t", default=10, type=int, help="Show top N values.", show_default=True)
@click.option(
    "--format", "-f", "fmt", default="auto",
    type=click.Choice(["auto", "json", "apache", "syslog"], case_sensitive=False),
)
@click.option("--numeric", "-N", is_flag=True, help="Compute percentiles for a numeric field.")
@click.option("--chart", "-c", is_flag=True, help="Show ASCII bar chart.")
def stats(
    file: Path,
    by: str,
    top: int,
    fmt: str,
    numeric: bool,
    chart: bool,
) -> None:
    """Show aggregate statistics for a log file.

    \b
    Examples:
      logpilot stats app.json
      logpilot stats app.json --by level --chart
      logpilot stats access.log --by status --top 5
      logpilot stats app.json --by latency_ms --numeric
    """
    from .aggregators.counter import Counter
    from .aggregators.percentiles import Percentiles
    from .visualization.tables import (
        print_counter_table,
        print_bar_chart,
        print_percentiles_table,
    )

    parser = AutoDetectParser(hint=fmt)
    counter: Counter = Counter(field=by)
    percentiles: Percentiles = Percentiles(field=by)
    total = 0

    for entry in parser.parse_file(str(file)):
        counter.add(entry)
        if numeric:
            percentiles.add(entry)
        total += 1

    console.print(f"\n[bold]File:[/bold] {file.name}  [bold]Total entries:[/bold] {total}")

    top_counts = counter.top(top)

    if numeric:
        summary = percentiles.summary()
        print_percentiles_table(summary, title=f"Percentile stats", field=by)
        if len(percentiles) < total:
            console.print(
                f"[dim]({total - len(percentiles)} entries had non-numeric or missing '{by}' field)[/dim]"
            )

    if chart:
        print_bar_chart(top_counts, title=f"Distribution by '{by}'", width=40)
    else:
        print_counter_table(top_counts, title=f"Top {top} by '{by}'", value_col=by.title(), count_col="Count")


# ── tail ─────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("file", type=click.Path(path_type=Path))
@click.option("--tui", is_flag=True, help="Launch full Textual TUI dashboard.")
@click.option("--filter", "-F", "filter_pattern", default="", help="Only show lines matching this regex.")
@click.option("--interval", default=0.25, type=float, help="Poll interval in seconds.", show_default=True)
@click.option(
    "--format", "-f", "fmt", default="auto",
    type=click.Choice(["auto", "json", "apache", "syslog"], case_sensitive=False),
)
def tail(
    file: Path,
    tui: bool,
    filter_pattern: str,
    interval: float,
    fmt: str,
) -> None:
    """Live tail a log file, streaming new lines as they appear.

    Use --tui for the full interactive Textual dashboard.

    \b
    Examples:
      logpilot tail /var/log/app.log
      logpilot tail /var/log/app.log --filter "ERROR"
      logpilot tail /var/log/app.log --tui
    """
    if tui:
        try:
            from .visualization.tui import run_dashboard
        except ImportError:
            err_console.print(
                "[red]Textual is not installed.[/red] Install it with:\n"
                "  pip install 'logpilot[tui]'"
            )
            sys.exit(1)
        run_dashboard(str(file), poll_interval=interval)
        return

    # Plain coloured stream tail
    parser = AutoDetectParser(hint=fmt)
    filter_re = re.compile(filter_pattern, re.IGNORECASE) if filter_pattern else None

    if not file.exists():
        # Wait for file to appear (useful for docker log paths)
        err_console.print(f"[yellow]Waiting for {file} to appear…[/yellow]")
        import time
        while not file.exists():
            time.sleep(interval)

    import time

    console.print(f"[dim]Tailing {file} (Ctrl+C to stop)[/dim]")
    offset = file.stat().st_size  # start from end

    try:
        while True:
            current_size = file.stat().st_size
            if current_size > offset:
                with file.open(encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    new_data = fh.read()
                    offset = fh.tell()

                for raw_line in new_data.splitlines():
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    if filter_re and not filter_re.search(raw_line):
                        continue
                    entry = parser.parse_line(raw_line)
                    if entry:
                        ts, level, msg = _entry_columns(entry)
                        colour = _level_colour(level)
                        console.print(f"[dim]{ts}[/dim] [{colour}]{level:8}[/{colour}] {msg}")
                    else:
                        console.print(raw_line)
            elif current_size < offset:
                # File was rotated
                offset = 0
                console.print("[yellow]— log rotated —[/yellow]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


if __name__ == "__main__":
    main()
