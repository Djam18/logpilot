# Usage Guide

## Parsing log files

logpilot auto-detects the format from the first non-empty line:

```bash
logpilot parse app.json          # JSON (NDJSON)
logpilot parse access.log        # Apache Combined (auto-detected)
logpilot parse /var/log/syslog   # Syslog RFC 3164 (auto-detected)
```

Force a specific format:

```bash
logpilot parse --format apache access.log
```

## Searching

```bash
# Case-insensitive regex across all fields
logpilot search --pattern "disk full" app.log

# Target a specific field
logpilot search --pattern "ERROR" --field level app.log

# Time-range filter (ISO-8601)
logpilot search --since 2025-10-01T00:00:00 --until 2025-10-02T00:00:00 app.log

# Combine: errors in the last 30 minutes
logpilot search --pattern "ERROR" --since "30m" app.log
```

## Aggregating statistics

```bash
# Top 10 HTTP status codes
logpilot stats --field status --top 10 access.log

# Percentiles of response time
logpilot stats --field response_ms --numeric app.log

# With ASCII bar chart
logpilot stats --field level --chart app.log
```

## Live tailing

```bash
# Simple coloured stream
logpilot tail /var/log/app.log

# Full Textual TUI dashboard
logpilot tail --tui /var/log/app.log
```

## Large files (parallel parsing)

```bash
# Auto-detect worker count (= CPU cores)
logpilot parse --workers 0 huge.log

# Explicit worker count
logpilot parse --workers 16 huge.log
```

## Python API quick reference

```python
from logpilot.parsers.auto_detect import AutoDetectParser
from logpilot.search.filter_chain import FilterChain
from logpilot.search.regex_search import RegexSearch
from logpilot.search.time_filter import TimeRangeFilter
from logpilot.aggregators.counter import Counter
from logpilot.aggregators.percentiles import Percentiles
from logpilot.alerts.rules import AlertRule, RulesEngine
from logpilot.alerts.slack import SlackChannel
from logpilot.alerts.anomaly import AnomalyDetector, AnomalyAlertPredicate
from logpilot.cache.redis_cache import QueryCache, make_cache_key
from datetime import datetime
import os

# --- Parse ---
parser = AutoDetectParser()

# --- Filter ---
chain = (
    FilterChain()
    .add(RegexSearch("error", fields=["message"]).matches)
    .add(TimeRangeFilter(start=datetime(2025, 10, 1)).matches)
)

# --- Aggregate ---
counter = Counter("level")
p = Percentiles("bytes")

# --- Alert ---
engine = RulesEngine()
engine.register_channel("slack", SlackChannel(os.environ["SLACK_WEBHOOK"]))
engine.add_rule(AlertRule(
    name="High error rate",
    predicate=lambda e: e.get("level") == "ERROR",
    cooldown=60,
    channels=["slack"],
))

# --- Anomaly detection ---
detector = AnomalyDetector(field="response_ms", threshold=3.5)
engine.add_rule(AlertRule(
    name="Latency anomaly",
    predicate=AnomalyAlertPredicate(detector),
    cooldown=30,
    channels=["slack"],
))

# --- Cache ---
cache = QueryCache(url=os.environ.get("LOGPILOT_CACHE_URL", "redis://localhost:6379"))
key = make_cache_key("/var/log/app.log", {"pattern": "error"})
results = cache.get(key)

if results is None:
    results = []
    for entry in parser.parse_file("/var/log/app.log"):
        if chain.matches(entry):
            results.append(entry)
            counter.add(entry)
            p.add(entry)
            engine.evaluate(entry)
    cache.set(key, results)

print(f"Matched {len(results)} entries")
print(counter.top(5))
print(p.summary())
```
