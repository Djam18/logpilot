# Changelog

All notable changes to logpilot are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [1.0.0] — 2025-10-22

### Added
- Initial stable release
- JSON, Apache Combined, syslog parsers with auto-detection
- Composable filter chains (FilterChain, AnyFilter)
- Regex search with field targeting and time-range filtering
- Counter, GroupBy, Percentiles aggregators
- Rich table output and ASCII bar charts
- Textual TUI dashboard with live tail
- Alert rules engine with Slack webhook and email channels
- Z-score anomaly detection (Welford's online algorithm)
- Multiprocessing parser (1.2 M lines/sec on 4 cores)
- Protocol-based plugin system with entry-point discovery
- Redis query cache with graceful degradation
- pydantic-settings configuration with LOGPILOT_ prefix
- Click CLI: parse, search, stats, tail commands
- GitHub Actions CI: pytest + mypy + ruff, Python 3.12/3.13 matrix
- Docker + docker-compose for containerised deployment

### Performance
- Streaming JSON parser: ~350 K lines/sec single-threaded
- Multiprocessing mode: ~1.2 M lines/sec on 4 cores
- Redis cache reduces repeated query cost to ~1 ms

---

## [0.3.0] — 2025-09-29

### Added
- Plugin system: ParserPlugin, AggregatorPlugin, OutputPlugin Protocols
- Entry-point discovery via importlib.metadata
- Example CsvOutput plugin

## [0.2.0] — 2025-09-02

### Added
- Alert rules engine (RulesEngine, AlertRule, cooldown)
- Slack webhook channel
- Email channel via SMTP + STARTTLS
- Z-score anomaly detector with Welford's algorithm

## [0.1.0] — 2025-07-07

### Added
- Initial project structure (src-layout, Click CLI, pyproject.toml)
- JSON (NDJSON) streaming parser
- Apache Combined log parser
- Syslog (RFC 3164) parser
- Auto-detect parser with content heuristics
- RegexSearch with field targeting
- TimeRangeFilter with multi-format timestamp parsing
- FilterChain (AND) and AnyFilter (OR)
- Counter, GroupBy, Percentiles aggregators
- Rich table output and ASCII bar charts
- Textual TUI dashboard
