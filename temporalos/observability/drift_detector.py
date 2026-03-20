"""Statistical drift detection for extraction output distributions.

Uses a rolling two-window approach:
  - Baseline window: first N samples, frozen once full
  - Current window: most recent M samples, checked against baseline

Statistical tests:
  - Confidence drift: Welch's t-test (no scipy required)
  - Topic distribution drift: symmetric KL divergence
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class DriftAlert:
    metric: str
    current_mean: float
    baseline_mean: float
    drift_score: float  # 0–1, higher = more drift
    is_drifted: bool
    message: str


@dataclass
class DriftReport:
    alerts: list[DriftAlert] = field(default_factory=list)
    window_size: int = 0
    baseline_size: int = 0

    @property
    def any_drift(self) -> bool:
        return any(a.is_drifted for a in self.alerts)

    def to_dict(self) -> dict:
        return {
            "any_drift": self.any_drift,
            "window_size": self.window_size,
            "baseline_size": self.baseline_size,
            "alerts": [
                {
                    "metric": a.metric,
                    "current_mean": round(a.current_mean, 4),
                    "baseline_mean": round(a.baseline_mean, 4),
                    "drift_score": round(a.drift_score, 4),
                    "is_drifted": a.is_drifted,
                    "message": a.message,
                }
                for a in self.alerts
            ],
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return sum((x - m) ** 2 for x in values) / (len(values) - 1)


def _welch_t_stat(a: list[float], b: list[float]) -> float:
    """Welch's t-statistic (unpaired, unequal variance). Pure Python, no scipy."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    va, vb = _variance(a), _variance(b)
    na, nb = len(a), len(b)
    # If both distributions have near-zero variance (uniform data), use mean diff
    if va < 1e-10 and vb < 1e-10:
        mean_diff = abs(_mean(a) - _mean(b))
        # Treat as effectively zero variance: t is infinite if means differ,
        # but cap to a large finite value proportional to the difference.
        return mean_diff * 1000.0
    denom = math.sqrt(va / na + vb / nb)
    if denom < 1e-15:
        return 0.0
    return abs(_mean(a) - _mean(b)) / denom


def _kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Symmetric KL divergence between two probability distributions."""
    keys = set(p) | set(q)
    eps = 1e-9
    kl = 0.0
    for k in keys:
        pk = p.get(k, eps)
        qk = q.get(k, eps)
        kl += pk * math.log(pk / qk + eps)
    return kl


class DriftDetector:
    """
    Detects distribution drift in extraction outputs.

    Maintains a frozen baseline window and a rolling current window.
    When the current window is large enough, statistical tests flag drift.
    """

    def __init__(
        self,
        baseline_size: int = 100,
        window_size: int = 50,
        confidence_threshold: float = 2.0,
        topic_kl_threshold: float = 0.3,
    ) -> None:
        self._baseline_size = baseline_size
        self._window_size = window_size
        self._confidence_t_threshold = confidence_threshold
        self._topic_kl_threshold = topic_kl_threshold
        self._lock = threading.Lock()

        self._baseline_confidence: list[float] = []
        self._baseline_topics: list[str] = []
        self._baseline_risk: list[str] = []

        self._window_confidence: Deque[float] = deque(maxlen=window_size)
        self._window_topics: Deque[str] = deque(maxlen=window_size)
        self._window_risk: Deque[str] = deque(maxlen=window_size)

        self._baseline_frozen: bool = False
        self._total_recorded: int = 0

    def record(self, confidence: float, topic: str, risk: str) -> None:
        with self._lock:
            self._total_recorded += 1
            if not self._baseline_frozen:
                self._baseline_confidence.append(confidence)
                self._baseline_topics.append(topic)
                self._baseline_risk.append(risk)
                if len(self._baseline_confidence) >= self._baseline_size:
                    self._baseline_frozen = True
            else:
                self._window_confidence.append(confidence)
                self._window_topics.append(topic)
                self._window_risk.append(risk)

    def check_drift(self) -> DriftReport:
        with self._lock:
            w_conf = list(self._window_confidence)
            b_conf = self._baseline_confidence[:]
            w_topics = list(self._window_topics)
            b_topics = self._baseline_topics[:]

        alerts: list[DriftAlert] = []

        # Confidence drift via Welch's t-test
        if len(w_conf) >= 10 and len(b_conf) >= 10:
            t = _welch_t_stat(w_conf, b_conf)
            score = min(t / 5.0, 1.0)
            drifted = t > self._confidence_t_threshold
            alerts.append(
                DriftAlert(
                    metric="confidence",
                    current_mean=_mean(w_conf),
                    baseline_mean=_mean(b_conf),
                    drift_score=score,
                    is_drifted=drifted,
                    message=(
                        f"Confidence drift detected (t={t:.2f})"
                        if drifted
                        else f"Confidence stable (t={t:.2f})"
                    ),
                )
            )

        # Topic distribution drift via KL divergence
        if len(w_topics) >= 10 and len(b_topics) >= 10:

            def to_dist(items: list[str]) -> dict[str, float]:
                counts: dict[str, int] = {}
                for x in items:
                    counts[x] = counts.get(x, 0) + 1
                total = len(items)
                return {k: v / total for k, v in counts.items()}

            kl = _kl_divergence(to_dist(w_topics), to_dist(b_topics))
            score = min(kl / 1.0, 1.0)
            drifted = kl > self._topic_kl_threshold
            alerts.append(
                DriftAlert(
                    metric="topic_distribution",
                    current_mean=kl,
                    baseline_mean=0.0,
                    drift_score=score,
                    is_drifted=drifted,
                    message=(
                        f"Topic distribution drift (KL={kl:.3f})"
                        if drifted
                        else f"Topics stable (KL={kl:.3f})"
                    ),
                )
            )

        return DriftReport(
            alerts=alerts,
            window_size=len(w_conf),
            baseline_size=len(b_conf),
        )

    @property
    def baseline_frozen(self) -> bool:
        return self._baseline_frozen

    @property
    def total_recorded(self) -> int:
        return self._total_recorded

    def reset(self) -> None:
        with self._lock:
            self._baseline_confidence.clear()
            self._baseline_topics.clear()
            self._baseline_risk.clear()
            self._window_confidence.clear()
            self._window_topics.clear()
            self._window_risk.clear()
            self._baseline_frozen = False
            self._total_recorded = 0


_detector: DriftDetector | None = None
_detector_lock = threading.Lock()


def get_drift_detector() -> DriftDetector:
    global _detector
    with _detector_lock:
        if _detector is None:
            _detector = DriftDetector()
    return _detector
