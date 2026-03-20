"""Confidence calibration analysis — ECE and reliability curves.

Expected Calibration Error (ECE) measures the gap between predicted confidence
and actual accuracy. A perfectly calibrated model has ECE = 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float  # fraction of samples in this bin that were correct


@dataclass
class CalibrationReport:
    ece: float  # Expected Calibration Error (0–1, lower is better)
    bins: list[CalibrationBin] = field(default_factory=list)
    total_samples: int = 0

    def to_dict(self) -> dict:
        return {
            "ece": round(self.ece, 4),
            "total_samples": self.total_samples,
            "bins": [
                {
                    "lower": b.lower,
                    "upper": b.upper,
                    "count": b.count,
                    "mean_confidence": round(b.mean_confidence, 4),
                    "accuracy": round(b.accuracy, 4),
                }
                for b in self.bins
            ],
        }


class ConfidenceCalibrator:
    """
    Tracks (confidence, correct) samples and computes calibration metrics.

    Usage:
        calibrator = ConfidenceCalibrator()
        calibrator.add_sample(confidence=0.8, correct=True)
        report = calibrator.compute()
    """

    def __init__(self, n_bins: int = 10) -> None:
        self._n_bins = n_bins
        self._samples: list[tuple[float, bool]] = []

    def add_sample(self, confidence: float, correct: bool) -> None:
        """Record a (confidence, correct) pair."""
        confidence = max(0.0, min(1.0, confidence))
        self._samples.append((confidence, correct))

    def compute(self) -> CalibrationReport:
        if not self._samples:
            return CalibrationReport(ece=0.0, bins=[], total_samples=0)

        bin_width = 1.0 / self._n_bins
        bins: list[CalibrationBin] = []
        ece = 0.0
        n = len(self._samples)

        for i in range(self._n_bins):
            lo = i * bin_width
            hi = lo + bin_width
            in_bin = [(c, ok) for c, ok in self._samples if lo <= c < hi]
            if not in_bin:
                continue

            mean_conf = sum(c for c, _ in in_bin) / len(in_bin)
            acc = sum(1 for _, ok in in_bin if ok) / len(in_bin)
            ece += (len(in_bin) / n) * abs(mean_conf - acc)

            bins.append(
                CalibrationBin(
                    lower=round(lo, 2),
                    upper=round(hi, 2),
                    count=len(in_bin),
                    mean_confidence=mean_conf,
                    accuracy=acc,
                )
            )

        return CalibrationReport(ece=ece, bins=bins, total_samples=n)

    def clear(self) -> None:
        self._samples.clear()

    @property
    def sample_count(self) -> int:
        return len(self._samples)
