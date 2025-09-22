"""Multiprocessing-based parser for large log files.

Strategy:
    1. Split the file into N byte-range chunks (one per CPU core).
    2. Each worker process parses its chunk independently using the
       auto-detect parser and returns a list of LogEntry dicts.
    3. Results are merged in order by the main process.

Throughput target: ≥1.2 M lines/sec on a 4-core machine with JSON logs.

Usage::

    from logpilot.perf.parallel_parser import parse_file_parallel

    entries = parse_file_parallel("huge.log", workers=8)
    print(f"Parsed {len(entries):,} entries")
"""
from __future__ import annotations

import os
from multiprocessing import Pool
from typing import Any

from ..parsers.auto_detect import AutoDetectParser

# Type alias for a byte range (start inclusive, end exclusive)
_Chunk = tuple[str, int, int]  # (path, start_byte, end_byte)


def _parse_chunk(args: _Chunk) -> list[dict[str, Any]]:
    """Worker function: parse lines in [start_byte, end_byte) from path."""
    path, start, end = args
    parser = AutoDetectParser()
    results: list[dict[str, Any]] = []

    with open(path, "rb") as fh:
        # Align to the next newline boundary if we're mid-line
        if start > 0:
            fh.seek(start - 1)
            ch = fh.read(1)
            if ch != b"\n":
                # Skip forward to the next full line
                fh.readline()
        else:
            fh.seek(0)

        while fh.tell() < end:
            raw = fh.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            entry = parser.parse_line(line)
            if entry is not None:
                results.append(entry)

    return results


def _split_file(path: str, n_chunks: int) -> list[_Chunk]:
    """Divide a file into n_chunks byte ranges."""
    size = os.path.getsize(path)
    if size == 0:
        return []
    chunk_size = max(size // n_chunks, 1)
    chunks: list[_Chunk] = []
    start = 0
    for i in range(n_chunks):
        end = start + chunk_size if i < n_chunks - 1 else size
        chunks.append((path, start, min(end, size)))
        start = end
        if start >= size:
            break
    return chunks


def parse_file_parallel(
    path: str,
    workers: int | None = None,
) -> list[dict[str, Any]]:
    """Parse a large log file using multiprocessing.

    Args:
        path:    Path to the log file.
        workers: Number of worker processes. Defaults to os.cpu_count().

    Returns:
        Ordered list of parsed log-entry dicts.
    """
    n = workers or os.cpu_count() or 4
    chunks = _split_file(path, n)
    if not chunks:
        return []

    if len(chunks) == 1:
        # Single chunk — skip multiprocessing overhead
        return _parse_chunk(chunks[0])

    with Pool(processes=n) as pool:
        results = pool.map(_parse_chunk, chunks)

    # Flatten ordered results
    return [entry for chunk_result in results for entry in chunk_result]


def benchmark(path: str, workers: int | None = None) -> dict[str, Any]:
    """Parse path and return throughput statistics."""
    import time

    start = time.perf_counter()
    entries = parse_file_parallel(path, workers=workers)
    elapsed = time.perf_counter() - start
    lines_per_sec = len(entries) / elapsed if elapsed > 0 else 0

    return {
        "entries": len(entries),
        "elapsed_sec": round(elapsed, 3),
        "lines_per_sec": round(lines_per_sec),
        "workers": workers or os.cpu_count(),
    }
