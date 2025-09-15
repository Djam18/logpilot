"""Z-score based anomaly detection for numeric log fields.

Detects statistical outliers in a streaming numeric field by comparing each
new value against a rolling mean and standard deviation.

Algorithm:
    z = (x - μ) / σ

A value is considered anomalous when |z| > threshold (default: 3.0).

The detector uses Welford's online algorithm for numerically stable
incremental mean and variance computation — no need to store all past values.

Reference: Welford, B. P. (1962). Note on a method for calculating corrected
           sums of squares and products. Technometrics, 4(3), 419–420.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnomalyDetector:
    """Detect z-score anomalies in a numeric log field.

    Attributes:
        field:          Log entry key to monitor (e.g. "response_time").
        threshold:      Z-score magnitude considered anomalous (default 3.0).
        min_samples:    Minimum observations before anomalies are reported.
                        Prevents false positives during warm-up.

    Usage::

        detector = AnomalyDetector(field="latency_ms", threshold=3.0)
        for entry in parser.parse_file("app.log"):
            result = detector.update(entry)
            if result.is_anomaly:
                print(f"Anomaly: z={result.z_score:.2f}, value={result.value}")
    """

    field: str
    threshold: float = 3.0
    min_samples: int = 30

    # Welford's online algorithm state (not part of public API)
    _n: int = field(default=0, init=False, repr=False)
    _mean: float = field(default=0.0, init=False, repr=False)
    _m2: float = field(default=0.0, init=False, repr=False)

    @property
    def count(self) -> int:
        return self._n

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def variance(self) -> float:
        return self._m2 / self._n if self._n > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def _welford_update(self, x: float) -> None:
        """Update running mean and M2 with Welford's algorithm."""
        self._n += 1
        delta = x - self._mean
        self._mean += delta / self._n
        delta2 = x - self._mean
        self._m2 += delta * delta2

    def update(self, entry: dict[str, Any]) -> "AnomalyResult":
        """Feed a log entry to the detector and return an AnomalyResult.

        Non-numeric or missing field values are ignored (result.skipped=True).
        """
        raw = entry.get(self.field)
        if raw is None:
            return AnomalyResult(value=None, z_score=None, is_anomaly=False, skipped=True)
        try:
            x = float(raw)
        except (TypeError, ValueError):
            return AnomalyResult(value=raw, z_score=None, is_anomaly=False, skipped=True)

        # Compute z-score against current distribution BEFORE updating it
        # so the current sample doesn't inflate the mean toward itself.
        if self._n >= self.min_samples and self.std > 0:
            z = abs(x - self._mean) / self.std
            is_anomaly = z > self.threshold
        else:
            z = None
            is_anomaly = False

        self._welford_update(x)
        return AnomalyResult(value=x, z_score=z, is_anomaly=is_anomaly, skipped=False)

    def reset(self) -> None:
        """Reset all accumulated state."""
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0


@dataclass(frozen=True)
class AnomalyResult:
    """Result returned by AnomalyDetector.update().

    Attributes:
        value:      The numeric value extracted from the entry (or raw if
                    conversion failed).
        z_score:    The computed |z| score, or None during warm-up.
        is_anomaly: True when |z| > threshold and min_samples is reached.
        skipped:    True when the field was absent or non-numeric.
    """

    value: float | Any | None
    z_score: float | None
    is_anomaly: bool
    skipped: bool = False


class AnomalyAlertPredicate:
    """Wraps AnomalyDetector as a predicate compatible with AlertRule.

    Usage::

        detector = AnomalyDetector(field="response_ms", threshold=3.5)
        rule = AlertRule(
            name="Response time anomaly",
            predicate=AnomalyAlertPredicate(detector),
            channels=["slack"],
        )
    """

    def __init__(self, detector: AnomalyDetector) -> None:
        self._detector = detector

    def __call__(self, entry: dict[str, Any]) -> bool:
        result = self._detector.update(entry)
        return result.is_anomaly
