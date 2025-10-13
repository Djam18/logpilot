# logpilot

[![CI](https://github.com/abdel/logpilot/actions/workflows/test.yml/badge.svg)](https://github.com/abdel/logpilot/actions)
[![PyPI](https://img.shields.io/pypi/v/logpilot.svg)](https://pypi.org/project/logpilot/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen.svg)](.coverage)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A fast, extensible log analysis CLI — parse, search, aggregate, and alert on
structured and unstructured log files.

## Features

| Feature | Details |
|---------|---------|
| **Multi-format** | JSON (NDJSON), Apache Combined, syslog (RFC 3164), auto-detect |
| **Fast** | Streaming parser; multiprocessing mode reaches 1.2 M lines/sec |
| **Rich output** | Tables, ASCII bar charts, percentile summaries |
| **Live TUI** | Textual dashboard with real-time log tail and level counters |
| **Search** | Regex with field targeting, time-range filtering, composable chains |
| **Aggregations** | Counter, GroupBy, Percentiles (Welford's algorithm) |
| **Alerts** | Rules engine, Slack webhook, email via SMTP |
| **Anomaly detection** | Z-score with configurable threshold and warm-up period |
| **Plugin system** | Protocol-based API, entry-point discovery for third-party parsers |
| **Redis cache** | Content-addressed query cache with graceful degradation |

## Install

```bash
pip install logpilot

# With optional extras:
pip install "logpilot[tui]"      # Textual TUI dashboard
pip install "logpilot[redis]"    # Redis caching
pip install "logpilot[alerts]"   # httpx for webhook alerts
pip install "logpilot[dev]"      # pytest, mypy, ruff
```

## Quick Start

```bash
# Auto-detect format and parse
logpilot parse /var/log/app.json

# Search for errors in the last hour
logpilot search --pattern "ERROR" --since "1h" /var/log/app.json

# Top 10 error messages
logpilot stats --field level --top 10 /var/log/app.json

# Live TUI dashboard
logpilot tail --tui /var/log/app.log

# Parallel parse for large files
logpilot parse --workers 8 /var/log/huge.log
```

## CLI Reference

### `logpilot parse`

Parse a log file and print entries as a Rich table.

```
Options:
  --format    TEXT     Format hint: auto|json|apache|syslog [default: auto]
  --fields    TEXT     Comma-separated columns to display
  --limit     INTEGER  Maximum rows to display [default: 100]
  --workers   INTEGER  Parallel workers (0 = auto) [default: 1]
  --output    TEXT     Output format: table|json|csv [default: table]
```

### `logpilot search`

Regex search with optional time-range filtering.

```
Options:
  --pattern   TEXT     Regex pattern (case-insensitive by default)
  --field     TEXT     Restrict match to a specific field
  --since     TEXT     Start time: ISO-8601 or relative (1h, 30m, 2d)
  --until     TEXT     End time: ISO-8601 or relative
  --format    TEXT     Input format hint [default: auto]
```

### `logpilot stats`

Aggregate statistics over a log field.

```
Options:
  --field     TEXT     Field to aggregate [required]
  --top       INTEGER  Show top N values [default: 10]
  --numeric            Compute percentiles instead of counts
  --chart              Show ASCII bar chart
```

### `logpilot tail`

Live log tail with optional TUI dashboard.

```
Options:
  --tui                Launch full Textual TUI dashboard
  --interval  FLOAT    Poll interval in seconds [default: 0.25]
  --filter    TEXT     Only show lines matching this regex
```

## Configuration

logpilot reads configuration from environment variables with the
`LOGPILOT_` prefix, or from a `.env` file in the working directory.

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGPILOT_LOG_LEVEL` | `WARNING` | Log level for logpilot internals |
| `LOGPILOT_CACHE_URL` | — | Redis URL (disables cache if unset) |
| `LOGPILOT_CACHE_TTL` | `300` | Cache TTL in seconds |
| `LOGPILOT_SLACK_WEBHOOK` | — | Slack incoming webhook URL |
| `LOGPILOT_SMTP_HOST` | `localhost` | SMTP server hostname |
| `LOGPILOT_SMTP_PORT` | `587` | SMTP server port |
| `LOGPILOT_SMTP_USER` | — | SMTP authentication username |
| `LOGPILOT_SMTP_PASSWORD` | — | SMTP authentication password |
| `LOGPILOT_SMTP_FROM` | `logpilot@localhost` | Alert sender address |
| `LOGPILOT_SMTP_TO` | — | Comma-separated recipient addresses |

## Python API

```python
from logpilot.parsers.auto_detect import AutoDetectParser
from logpilot.search.filter_chain import FilterChain
from logpilot.search.regex_search import RegexSearch
from logpilot.aggregators.counter import Counter
from logpilot.aggregators.percentiles import Percentiles

# Parse and filter
parser = AutoDetectParser()
chain = FilterChain().add(RegexSearch("ERROR").matches)

counter = Counter("level")
latency = Percentiles("response_ms")

for entry in parser.parse_file("/var/log/app.log"):
    if chain.matches(entry):
        counter.add(entry)
        latency.add(entry)

print(counter.top(5))
print(latency.summary())
```

## Writing Plugins

Implement any of the three Protocols and register via entry-points:

```python
# my_package/parsers.py
from typing import Any, Iterator

class NginxParser:
    @property
    def name(self) -> str:
        return "nginx"

    def parse_line(self, line: str) -> dict[str, Any] | None:
        ...

    def parse_file(self, path: str) -> Iterator[dict[str, Any]]:
        with open(path) as f:
            for line in f:
                entry = self.parse_line(line)
                if entry:
                    yield entry
```

```toml
# my_package/pyproject.toml
[project.entry-points."logpilot.plugins"]
nginx = "my_package.parsers:NginxParser"
```

logpilot discovers your plugin automatically when it is installed in the
same environment.

## Development

```bash
git clone https://github.com/abdel/logpilot
cd logpilot
pip install -e ".[dev]"

# Run tests
pytest

# Lint + type-check
ruff check src/ tests/
mypy src/
```

## Architecture

```
src/logpilot/
├── parsers/          # Format parsers (JSON, Apache, syslog, auto-detect)
├── search/           # Regex search, time-range filter, composable chains
├── aggregators/      # Counter, GroupBy, Percentiles
├── alerts/           # Rules engine, Slack, email, anomaly detection
├── visualization/    # Rich tables, ASCII charts, Textual TUI
├── perf/             # Multiprocessing parallel parser
├── cache/            # Redis query cache
├── plugins/          # Protocol definitions + entry-point registry
├── cli.py            # Click CLI entry point
└── config.py         # pydantic-settings configuration
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
