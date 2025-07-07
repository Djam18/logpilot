"""Logpilot CLI — entry point.

Usage:
    logpilot parse <file>              # Parse and display log entries
    logpilot search <file> <pattern>   # Search with regex
    logpilot stats <file>              # Aggregate statistics
    logpilot tail <file>               # Live tail with TUI
    logpilot alert <file>              # Check alert rules
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from .parsers.json_parser import JsonParser
from .parsers.auto_detect import AutoDetectParser

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Logpilot — fast log analysis CLI."""


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", default="auto", help="Log format: auto|json|apache|syslog")
@click.option("--limit", "-n", default=0, help="Max lines to show (0 = all)")
@click.option("--json-out", is_flag=True, help="Output as JSON")
def parse(file: str, fmt: str, limit: int, json_out: bool) -> None:
    """Parse a log file and display entries."""
    parser = AutoDetectParser(hint=fmt)
    count = 0

    for entry in parser.parse_file(file):
        if limit and count >= limit:
            break

        if json_out:
            import json
            click.echo(json.dumps(entry))
        else:
            level = str(entry.get("level", entry.get("severity", "INFO"))).upper()
            msg = entry.get("message", entry.get("msg", str(entry)))
            timestamp = entry.get("timestamp", entry.get("time", entry.get("@timestamp", "")))
            color = {"ERROR": "red", "WARN": "yellow", "WARNING": "yellow", "DEBUG": "dim"}.get(
                level, "white"
            )
            console.print(f"[dim]{timestamp}[/dim] [{color}]{level:7}[/{color}] {msg}")

        count += 1

    console.print(f"\n[dim]Parsed {count} entries from {file}[/dim]")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("pattern")
@click.option("--format", "-f", "fmt", default="auto")
@click.option("--case-insensitive", "-i", is_flag=True)
def search(file: str, pattern: str, fmt: str, case_insensitive: bool) -> None:
    """Search log entries matching a regex pattern."""
    import re
    from .search.regex_search import RegexSearch

    flags = re.IGNORECASE if case_insensitive else 0
    searcher = RegexSearch(pattern=pattern, flags=flags)
    parser = AutoDetectParser(hint=fmt)
    count = 0

    for entry in parser.parse_file(file):
        if searcher.matches(entry):
            msg = entry.get("message", entry.get("msg", str(entry)))
            console.print(str(msg))
            count += 1

    console.print(f"\n[dim]{count} matches[/dim]")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--by", default="level", help="Field to group by")
@click.option("--format", "-f", "fmt", default="auto")
def stats(file: str, by: str, fmt: str) -> None:
    """Show aggregate statistics for a log file."""
    from .aggregators.counter import Counter
    from rich.table import Table

    parser = AutoDetectParser(hint=fmt)
    counter: Counter = Counter(field=by)

    for entry in parser.parse_file(file):
        counter.add(entry)

    table = Table(title=f"Stats by '{by}'")
    table.add_column("Value", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for value, count in counter.top(20):
        table.add_row(str(value), str(count))

    console.print(table)


if __name__ == "__main__":
    main()
