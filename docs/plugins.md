# Writing logpilot Plugins

logpilot uses Python's `typing.Protocol` (structural subtyping) for its plugin
API. You never need to inherit from a logpilot class — any class that
implements the required methods is a valid plugin.

## Plugin types

### ParserPlugin

Teach logpilot to understand a new log format.

```python
from typing import Any, Iterator

class NginxParser:
    @property
    def name(self) -> str:
        return "nginx"

    def parse_line(self, line: str) -> dict[str, Any] | None:
        """Return a dict on success, None to skip the line."""
        ...

    def parse_file(self, path: str) -> Iterator[dict[str, Any]]:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = self.parse_line(line.strip())
                if entry is not None:
                    yield entry
```

### AggregatorPlugin

Add a custom aggregation that accumulates values as entries flow through.

```python
from typing import Any

class MedianAggregator:
    def __init__(self, field: str) -> None:
        self._field = field
        self._values: list[float] = []

    @property
    def name(self) -> str:
        return "median"

    def add(self, entry: dict[str, Any]) -> None:
        try:
            self._values.append(float(entry[self._field]))
        except (KeyError, TypeError, ValueError):
            pass

    def result(self) -> dict[str, Any]:
        if not self._values:
            return {"median": None}
        s = sorted(self._values)
        mid = len(s) // 2
        median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
        return {"median": median, "count": len(s)}
```

### OutputPlugin

Render a list of log entries in a custom format.

```python
from typing import Any
import json

class JsonLinesOutput:
    @property
    def name(self) -> str:
        return "jsonl"

    def render(self, entries: list[dict[str, Any]]) -> str:
        return "\n".join(json.dumps(e, default=str) for e in entries)
```

## Registering plugins via entry-points

Add this to your package's `pyproject.toml`:

```toml
[project.entry-points."logpilot.plugins"]
nginx   = "my_package.parsers:NginxParser"
median  = "my_package.aggregators:MedianAggregator"
jsonl   = "my_package.outputs:JsonLinesOutput"
```

When your package is installed in the same environment as logpilot, the
`PluginRegistry.discover()` call will pick up your plugins automatically.

## Runtime registration

You can also register plugins directly at runtime:

```python
from logpilot.plugins.registry import default_registry

default_registry.register_parser(NginxParser())
default_registry.register_aggregator(MedianAggregator("response_ms"))
default_registry.register_output(JsonLinesOutput())

# List available plugins
print(default_registry.list_parsers())
# ['json', 'apache', 'syslog', 'nginx']
```

## Validation

`PluginRegistry.register_*()` uses `isinstance(plugin, Protocol)` to validate
the plugin before registering it. If your class is missing a required method or
property, registration raises `TypeError` with a clear message.

## Testing plugins

```python
from logpilot.plugins.base import ParserPlugin
from my_package.parsers import NginxParser

def test_nginx_parser_implements_protocol():
    p = NginxParser()
    assert isinstance(p, ParserPlugin)

def test_nginx_parse_line():
    p = NginxParser()
    line = '192.168.1.1 - - [01/Oct/2025:10:00:00 +0000] "GET / HTTP/1.1" 200 512'
    entry = p.parse_line(line)
    assert entry is not None
    assert entry["status"] == 200
```
