# logpilot

[![CI](https://github.com/abdel/logpilot/actions/workflows/test.yml/badge.svg)](https://github.com/abdel/logpilot/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A fast, extensible log analysis CLI — parse, search, aggregate, alert.

## Features

- **Multi-format**: JSON, Apache (Common/Combined), syslog, auto-detect
- **Fast**: streaming parser, 1M+ lines/sec
- **Rich output**: tables, bar charts, live TUI dashboard
- **Alerts**: Slack webhook, email via SMTP
- **Extensible**: plugin system via Protocol-based API
- **Caching**: Redis cache for repeated queries

## Install

```bash
pip install logpilot
```

## Usage

```bash
# Parse a log file
logpilot parse app.log

# Search with regex
logpilot search app.log "ERROR.*database"

# Aggregate stats by level
logpilot stats app.log --by level

# Live tail with TUI
logpilot tail app.log

# Check alert rules
logpilot alert app.log --rules rules.yml
```

## Development

```bash
git clone https://github.com/abdel/logpilot
cd logpilot
pip install -e ".[dev]"
pytest
```
