# logpilot — Project Overview

A complete picture of what was built, version by version, with every feature,
sub-feature, and the rationale behind each decision.

---

## Table of Contents

- [Vision](#vision)
- [Versions at a Glance](#versions-at-a-glance)
- [v0.1.0 — Foundation (Jul 2025)](#v010--foundation-jul-2025)
- [v0.2.0 — Alerting (Sep 2025)](#v020--alerting-sep-2025)
- [v0.3.0 — Extensibility (Sep–Oct 2025)](#v030--extensibility-sepoct-2025)
- [v1.0.0 — Stable Release (Oct 2025)](#v100--stable-release-oct-2025)
- [v1.0.1 — Bug Fixes (Dec 2025)](#v101--bug-fixes-dec-2025)
- [Architecture Decisions](#architecture-decisions)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Vision

logpilot answers one question: **"What is happening in my logs right now?"**

Most log tools are either too heavy (Elasticsearch + Kibana) or too primitive
(`grep` + `awk`). logpilot sits in the middle: a single installable CLI that
parses, searches, aggregates, and alerts — no server, no configuration file
required for common cases, no dependency on a running service.

Target users: developers and SREs who want log insight in seconds from a
terminal, a Docker container, or a CI pipeline.

---

## Versions at a Glance

| Version | Date | Theme | Commits |
|---------|------|-------|---------|
| v0.1.0 | Jul–Aug 2025 | Foundation: parsers, search, output | 8 |
| v0.2.0 | Sep 2025 | Alerting: rules, Slack, email, anomaly | 4 |
| v0.3.0 | Sep–Oct 2025 | Extensibility: plugins, Redis, docs | 4 |
| v1.0.0 | Oct 2025 | Stable: CI/CD, Docker, packaging, coverage | 4 |
| v1.0.1 | Dec 2025 | Bug fixes found during real-world testing | 5 |

---

## v0.1.0 — Foundation (Jul–Aug 2025)

**Goal:** Parse any common log format, search it, show useful output.

### Parsers

| Sub-feature | What it does | File |
|-------------|-------------|------|
| JSON (NDJSON) | Streams newline-delimited JSON line by line; no full-file load | `parsers/json_parser.py` |
| Apache Combined | Regex-parses the CLF access log format; maps status to int, bytes to int | `parsers/apache.py` |
| Syslog RFC 3164 | Parses `<priority>Month DD HH:MM:SS host tag: msg`; extracts facility/severity | `parsers/syslog.py` |
| Auto-detect | Reads first non-empty line; applies heuristics (leading `{` → JSON, CLF regex → Apache, month prefix → syslog) | `parsers/auto_detect.py` |

**Decision:** Auto-detect locks the format after the first matched line. This
avoids re-probing every line at the cost of failing on mixed-format files
(documented limitation). In practice, log files are never mixed.

### Search

| Sub-feature | What it does | File |
|-------------|-------------|------|
| RegexSearch | Matches a compiled pattern against all fields (or a specified field) of each entry | `search/regex_search.py` |
| TimeRangeFilter | Parses entry timestamps in 6 formats; filters by ISO-8601 `--since` / `--until` | `search/time_filter.py` |
| FilterChain | Composes predicates with AND semantics; fluent `.add()` API | `search/filter_chain.py` |
| AnyFilter | OR-semantics variant of FilterChain | `search/filter_chain.py` |

**Decision:** Predicates are plain callables `(entry: dict) -> bool`. This
keeps the filter system composable without a DSL or query language. The
tradeoff is that complex queries (e.g., `field > 500`) require Python code
rather than a CLI expression. A future version could add an expression parser.

### Aggregators

| Sub-feature | What it does | File |
|-------------|-------------|------|
| Counter | `collections.Counter` wrapper; `.top(n)` returns sorted list | `aggregators/counter.py` |
| GroupBy | Groups entries by field value into bucketed lists | `aggregators/groupby.py` |
| Percentiles | Welford's online algorithm for single-pass mean/variance; nearest-rank p50/p90/p95/p99 | `aggregators/percentiles.py` |

**Decision:** Welford's algorithm was chosen for Percentiles so the entire
file does not need to be loaded into memory. The tradeoff is approximate
percentiles (nearest-rank), which is acceptable for log analysis.

### Output

| Sub-feature | What it does | File |
|-------------|-------------|------|
| Rich table | Coloured, rounded-border table; rows coloured by log level (ERROR=red, WARN=yellow) | `visualization/tables.py` |
| ASCII bar chart | `█` block characters scaled to max value; shows count and percentage | `visualization/tables.py` |
| Percentile table | Two-column Rich table: metric name + value | `visualization/tables.py` |
| Textual TUI | Full-screen `textual` dashboard: live log view, top-fields panel, stats bar, keybindings (q/p/c) | `visualization/tui.py` |
| Stream output | One coloured line per entry: `[dim]timestamp[/dim] [colour]LEVEL[/colour] message` | `cli.py` |

---

## v0.2.0 — Alerting (Sep 2025)

**Goal:** Notify humans when something goes wrong, without requiring a
monitoring platform.

### Alert Rules Engine

| Sub-feature | What it does | File |
|-------------|-------------|------|
| AlertRule | Dataclass: name, predicate, cooldown (default 60 s), list of channel IDs | `alerts/rules.py` |
| RulesEngine | Evaluates all rules against each entry; enforces cooldown per rule; returns fired rule names | `alerts/rules.py` |
| AlertChannel | Abstract base; `send(rule_name, entry)` interface | `alerts/rules.py` |

**Decision:** Cooldown is implemented as a per-rule `last_fired` timestamp in
memory. This means cooldowns reset on restart. A persistent store (Redis,
SQLite) would fix this but adds a dependency. For v1.0 the in-memory approach
is fine for daemon/sidecar use.

### Notification Channels

| Sub-feature | What it does | File |
|-------------|-------------|------|
| SlackChannel | Posts Block Kit message to an Incoming Webhook URL via `urllib` (no httpx dep) | `alerts/slack.py` |
| EmailChannel | Sends via `smtplib` with STARTTLS; supports multiple recipients; uses `MIMEMultipart` | `alerts/email_channel.py` |

**Decision:** `urllib` (stdlib) was used for Slack to avoid requiring `httpx`
in the base install. `httpx` is available as an optional `[alerts]` extra for
users who want async channels.

### Anomaly Detection

| Sub-feature | What it does | File |
|-------------|-------------|------|
| AnomalyDetector | Welford's online mean/variance; computes z-score per entry; configurable threshold (default 3σ) and warm-up period (default 30 samples) | `alerts/anomaly.py` |
| AnomalyResult | Frozen dataclass: field, value, z_score, mean, std, is_anomaly | `alerts/anomaly.py` |
| AnomalyAlertPredicate | Wraps AnomalyDetector as a FilterChain-compatible predicate | `alerts/anomaly.py` |

**Decision:** Z-score is computed **before** updating the Welford running
stats. Computing after would pull the mean toward the anomalous value,
reducing sensitivity for outliers. This is a subtle but important correctness
detail.

---

## v0.3.0 — Extensibility (Sep–Oct 2025)

**Goal:** Let users extend logpilot without forking it.

### Plugin System

| Sub-feature | What it does | File |
|-------------|-------------|------|
| ParserPlugin Protocol | `parse_line(line) -> dict | None`; `format_name` property | `plugins/base.py` |
| AggregatorPlugin Protocol | `add(entry)`; `result() -> dict` | `plugins/base.py` |
| OutputPlugin Protocol | `write(entry)`; `flush()` | `plugins/base.py` |
| PluginRegistry | Discovers plugins via `importlib.metadata` entry points (`logpilot.parsers`, `logpilot.aggregators`, `logpilot.outputs`) | `plugins/registry.py` |
| CsvOutput example | Reference OutputPlugin that writes CSV to stdout or a file path | `plugins/examples/csv_output.py` |

**Decision:** `@runtime_checkable Protocol` was chosen over ABC so that
third-party classes implementing the interface duck-typing don't need to
inherit from a logpilot base class. `isinstance()` checks still work for
registry validation.

### Redis Cache

| Sub-feature | What it does | File |
|-------------|-------------|------|
| make_cache_key | SHA-256 of `(path, params_json)` → `logpilot:cache:{digest}` | `cache/redis_cache.py` |
| QueryCache | `get/set/invalidate/flush`; JSON-serialises entry lists; `available` property for graceful degradation | `cache/redis_cache.py` |

**Decision:** All Redis operations are wrapped in `try/except`. If Redis is
unavailable the cache silently no-ops — logpilot still works, just without
caching. This avoids making Redis a hard dependency.

---

## v1.0.0 — Stable Release (Oct 2025)

**Goal:** Production-ready: tested, documented, containerised, installable.

### Infrastructure

| Sub-feature | What it does | File |
|-------------|-------------|------|
| Dockerfile | Multi-stage: `python:3.12-slim` builder builds wheel; runtime stage installs wheel as non-root user; `/logs` volume mount | `Dockerfile` |
| docker-compose | `logpilot` service + `redis:7-alpine` with health-check | `docker-compose.yml` |
| GitHub Actions CI | 3 jobs: `test` (pytest matrix 3.12/3.13 + Redis service), `lint` (ruff + mypy --strict), `docker` (build check) | `.github/workflows/test.yml` |
| pyproject.toml | `setuptools.build_meta`, src-layout, entry point `logpilot = logpilot.cli:main`, optional extras (`tui`, `redis`, `alerts`, `dev`) | `pyproject.toml` |

### Documentation

| Sub-feature | What it does | File |
|-------------|-------------|------|
| README | Feature table, install variants, full CLI reference, config table, Python API example | `README.md` |
| CHANGELOG | Keep-a-Changelog format, all versions from v0.1.0 | `CHANGELOG.md` |
| Usage guide | Practical CLI examples for every command + Python API recipes | `docs/usage.md` |
| Plugin guide | Step-by-step guide to implementing all 3 protocol types | `docs/plugins.md` |

### Performance Research

| Sub-feature | What it does | File |
|-------------|-------------|------|
| JIT benchmark | Measures NDJSON parse throughput with/without `PYTHON_JIT=1` on Python 3.13; documents ~20% speedup on hot loops | `perf/jit_experiment.py` |
| t-string templates | Python 3.14 PEP 750 demo: XSS-safe HTML rendering and injection-safe SQL via template processor; compat shim for < 3.14 | `visualization/templates.py` |

---

## v1.0.1 — Bug Fixes (Dec 2025)

**Goal:** Fix issues discovered by running the CLI against real log files.

### Issues Found and Fixed

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `pip install logpilot` fails | `dependencies` array was inside `[project.urls]` TOML section instead of `[project]` — a missing blank line caused the parser to nest it under URLs | Moved `dependencies` above `[project.urls]` |
| `parse --output table` (Apache): shows `None` columns | `cols = list(entry.keys())` includes `referrer`, `user_agent`, `protocol` which are always `None` for simple access logs | Smart column selection: skip fields whose first-row value is `None` and that are in the known nullable Apache set |
| `search --output table` (Apache): same `None` column issue | Same root cause, different command | Same fix applied to search table renderer |
| `search` matched wrong entries | `RegexSearch.matches()` was called with no `fields` argument, matching against the full `str(entry)` representation including keys | Fixed field targeting: `--field` now correctly passes `fields=[field]` to `RegexSearch` |
| Apache stream output: raw dict | `_entry_columns()` was missing in the old CLI; stream output fell through to `str(entry.get("message") or "")` which was empty for Apache entries | Added `_entry_columns()` with format detection: Apache → `METHOD /path → STATUS (N B)`, syslog → `[tag] message` |
| `tail` command missing | Referenced in README and docs but the Click command was never added to `cli.py` | Implemented `tail` command: byte-offset polling, log-rotation detection (size shrink), `--filter` regex, `--tui` for Textual |

---

## Architecture Decisions

### Why src-layout?

`src/logpilot/` instead of `logpilot/` at the root prevents the package from
being accidentally importable without installation, which would mask missing
`__init__.py` files and entry-point wiring during development.

### Why Click over Typer?

Click is more mature, has stable API guarantees, and avoids a Typer/FastAPI
dependency chain. Typer's automatic type-annotation parsing is convenient but
adds ~1 s import time in some environments.

### Why pydantic-settings for config?

pydantic-settings gives typed, validated config from environment variables and
`.env` files in ~10 lines. The `LOGPILOT_` prefix prevents collisions. In
earlier prototypes `os.environ.get()` with manual type coercion was fragile
and untested.

### Why not SQLite for persistent cache?

SQLite would add file locking complexity and a migration story. Redis is the
natural choice for a cache that may be shared across multiple logpilot
processes (e.g., in a Kubernetes sidecar scenario). The `[redis]` extra makes
it opt-in.

### Why Welford's algorithm everywhere?

Both `Percentiles` and `AnomalyDetector` use Welford's online mean/variance.
It gives numerically stable single-pass statistics with O(1) memory regardless
of file size. The alternative (store all values, compute offline) would fail
on log files > available RAM.

---

## Known Limitations

| Limitation | Severity | Workaround |
|-----------|----------|------------|
| Mixed-format log files (e.g., JSON + Apache in same file) | Medium | Split the file before parsing |
| Apache timestamp not parsed to ISO-8601 | Low | Pass raw timestamp to `TimeRangeFilter` (it tries 6 formats) |
| Anomaly cooldown resets on restart | Low | Use Redis for persistent last-fired timestamps (future) |
| TUI requires `textual>=0.50`; not in base install | Low | `pip install 'logpilot[tui]'` |
| `stats --numeric` percentiles are nearest-rank (approximate) | Low | Acceptable for log analysis; exact percentiles require O(n) memory |
| No Windows support for `tail` (uses POSIX seek/stat) | Medium | Use WSL or Docker |

---

## Roadmap

### v1.1.0 (planned)
- [ ] `logpilot export` command: write filtered results to CSV/Parquet
- [ ] `logpilot alert daemon` — background process watching a file and firing alerts
- [ ] Apache timestamp → ISO-8601 normalisation in the parser
- [ ] `--since` / `--until` support for `stats` command

### v1.2.0 (planned)
- [ ] Expression filter language: `level == "ERROR" AND latency_ms > 500`
- [ ] OpenTelemetry log format parser
- [ ] Persistent anomaly state via Redis
- [ ] Windows compatibility for `tail`

### v2.0.0 (future)
- [ ] TUI redesign: filterable log stream, command palette, bookmarks
- [ ] Web UI server mode: `logpilot serve --port 8080`
- [ ] Multi-file support: `logpilot stats /var/log/*.log`
