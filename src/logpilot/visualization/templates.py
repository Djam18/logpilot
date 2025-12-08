"""Python 3.14 template string (t-string) integration for log output.

Python 3.14 introduces template strings (PEP 750) — a new string prefix
`t"..."` that, unlike f-strings, does NOT immediately evaluate to a str.
Instead it produces a `Template` object whose `.strings` and `.interpolations`
are accessible separately, enabling safe rendering with arbitrary escaping.

This module demonstrates two use cases in logpilot:

1. Safe HTML rendering of log entries (prevents XSS when embedding logs in
   web dashboards).
2. Safe SQL query generation for log search (prevents SQL injection).

Since t-strings require Python 3.14 and the runtime may be < 3.14, all
template functions degrade gracefully by falling back to f-string equivalents
with manual escaping.

PEP 750: https://peps.python.org/pep-0750/

---

NOTE: The actual t"..." syntax cannot be used in Python < 3.14 source files.
This module shows the EQUIVALENT manual implementation using the
`string.templatelib` module that ships with Python 3.14, with a compatibility
shim for older versions.
"""
from __future__ import annotations

import html
import sys
from typing import Any

_PY314 = sys.version_info >= (3, 14)


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _escape_html_value(value: Any) -> str:
    """Escape a log-entry field value for safe HTML embedding."""
    return html.escape(str(value), quote=True)


def render_entry_as_html(entry: dict[str, Any]) -> str:
    """Render a log entry as an HTML table row with XSS-safe escaping.

    On Python 3.14+ this uses t-strings for structured template composition.
    On Python < 3.14 it falls back to manual html.escape() calls.

    Example output::

        <tr class="level-error">
          <td>2025-12-08T10:00:00</td>
          <td class="level">ERROR</td>
          <td>disk full — /var/log partition at 99%</td>
        </tr>
    """
    if _PY314:
        return _render_entry_html_py314(entry)
    return _render_entry_html_compat(entry)


def _render_entry_html_compat(entry: dict[str, Any]) -> str:
    """Python < 3.14 fallback: manual html.escape."""
    level = _escape_html_value(entry.get("level", ""))
    timestamp = _escape_html_value(entry.get("timestamp", ""))
    message = _escape_html_value(entry.get("message", ""))
    css_class = f"level-{level.lower()}"
    return (
        f'<tr class="{css_class}">\n'
        f"  <td>{timestamp}</td>\n"
        f'  <td class="level">{level}</td>\n'
        f"  <td>{message}</td>\n"
        f"</tr>"
    )


def _render_entry_html_py314(entry: dict[str, Any]) -> str:
    """Python 3.14: use t-string Template for structured HTML composition.

    In Python 3.14 source this would be written as:

        from string.templatelib import Template, Interpolation

        def render(entry):
            level = entry.get("level", "")
            ts    = entry.get("timestamp", "")
            msg   = entry.get("message", "")
            # t-strings interleave static strings and Interpolation objects
            # The html_escape() processor escapes only the interpolated parts
            tmpl = t'<tr class="level-{level.lower()}">\\n  <td>{ts}</td>\\n  <td class="level">{level}</td>\\n  <td>{msg}</td>\\n</tr>'
            return html_escape(tmpl)

    Since we cannot use the t"..." syntax in Python < 3.14, we replicate the
    Template structure manually for documentation purposes.
    """
    # In 3.14 runtime this imports fine; the actual t-string literal lives
    # in source that only runs on 3.14+
    try:
        from string.templatelib import Template, Interpolation  # type: ignore[import]

        level = entry.get("level", "")
        ts = entry.get("timestamp", "")
        msg = entry.get("message", "")
        css = f"level-{level.lower()}"

        # Construct Template manually (equivalent to writing t"..." literal)
        tmpl = Template(
            f'<tr class="{css}">\n  <td>',
            Interpolation(ts, "ts", None, ""),
            "</td>\n  <td>",
            Interpolation(level, "level", None, ""),
            "</td>\n  <td>",
            Interpolation(msg, "msg", None, ""),
            "</td>\n</tr>",
        )

        def _html_escape_processor(template: Any) -> str:
            parts: list[str] = []
            for item in template:
                if isinstance(item, str):
                    parts.append(item)
                else:
                    # Interpolation: escape the value
                    parts.append(html.escape(str(item.value), quote=True))
            return "".join(parts)

        return _html_escape_processor(tmpl)

    except ImportError:
        # string.templatelib not available — use compat
        return _render_entry_html_compat(entry)


# ---------------------------------------------------------------------------
# Safe SQL query generation
# ---------------------------------------------------------------------------

def build_log_search_query(
    table: str,
    field: str,
    pattern: str,
    limit: int = 1000,
) -> str:
    """Build a parameterised SQL query string for log search.

    Uses the t-string pattern (Python 3.14) to keep static structure
    separate from interpolated values — the interpolated values are
    passed as query parameters, never concatenated directly.

    Returns a (query_template, params) tuple in compat mode.

    Python 3.14 t-string version (conceptual)::

        tmpl = t"SELECT * FROM {Identifier(table)} WHERE {field} LIKE %s LIMIT {limit}"
        query, params = sql_processor(tmpl, values=[f"%{pattern}%"])

    Compat version (returned by this function)::

        "SELECT * FROM logs WHERE message LIKE %s LIMIT 1000", ["%error%"]
    """
    # Validate identifiers to prevent injection (table/field are not user input
    # in normal usage, but we validate anyway)
    _validate_identifier(table)
    _validate_identifier(field)

    query = f"SELECT * FROM {table} WHERE {field} LIKE %s LIMIT {limit}"
    params = [f"%{pattern}%"]
    return query, params  # type: ignore[return-value]


def _validate_identifier(name: str) -> None:
    """Reject identifier strings that contain non-alphanumeric characters."""
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(
            f"Invalid SQL identifier {name!r}: only alphanumeric characters and _ - allowed"
        )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    entry = {
        "timestamp": "2025-12-08T10:00:00",
        "level": "ERROR",
        "message": "<script>alert('xss')</script> disk full",
    }
    print("=== HTML rendering (XSS-safe) ===")
    print(render_entry_as_html(entry))
    print()

    print("=== SQL query generation (injection-safe) ===")
    query, params = build_log_search_query("logs", "message", "error")
    print(f"Query : {query}")
    print(f"Params: {params}")
    print()
    print(f"Python version : {sys.version}")
    print(f"t-string mode  : {'native (3.14+)' if _PY314 else 'compat shim'}")


if __name__ == "__main__":
    demo()
