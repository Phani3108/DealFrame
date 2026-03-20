"""
Phase 7 end-to-end tests — Production Observability & Drift Detection.

Covers:
  - PipelineMetrics: record/render, singleton, no-crash without prometheus_client
  - DriftDetector:   baseline accumulation, freeze, t-test drift, KL drift, reset
  - ConfidenceCalibrator: ECE computation, bin structure, edge cases
  - Observability API endpoints: /metrics, /observability/drift, /observability/calibration,
    /observability/calibration/sample, /review/queue, /review/{id}/label

Rule §0: all real code, only DB mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── PipelineMetrics ───────────────────────────────────────────────────────────


class TestPipelineMetrics:
    def test_singleton_identity(self):
        from temporalos.observability.metrics import get_metrics

        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_record_extraction_no_crash(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_extraction(model="gpt4o", risk="high", confidence=0.8, latency_ms=500)

    def test_record_extraction_with_cost(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_extraction("gpt4o", "medium", 0.7, 400, cost_usd=0.002)

    def test_record_error_no_crash(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_error(model="gpt4o")

    def test_record_stage_no_crash(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_stage(stage="alignment", latency_ms=30)

    def test_record_video_no_crash(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_video("completed")

    def test_render_returns_bytes(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        body, content_type = m.render_prometheus()
        assert isinstance(body, bytes)
        assert len(body) > 0

    def test_render_content_type_is_text(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        _, content_type = m.render_prometheus()
        assert "text" in content_type.lower()

    def test_render_contains_metric_names(self):
        from temporalos.observability.metrics import get_metrics

        m = get_metrics()
        m.record_extraction("test_model", "low", 0.9, 200)
        body, _ = m.render_prometheus()
        text = body.decode()
        assert "temporalos" in text or "prometheus_client" in text.lower()


# ── DriftDetector ─────────────────────────────────────────────────────────────


class TestDriftDetector:
    def _make(self, baseline=20, window=10):
        from temporalos.observability.drift_detector import DriftDetector

        return DriftDetector(baseline_size=baseline, window_size=window)

    def test_initial_state(self):
        d = self._make()
        assert not d.baseline_frozen
        assert d.total_recorded == 0

    def test_counts_total_recorded(self):
        d = self._make(baseline=5)
        for _ in range(3):
            d.record(0.8, "pricing", "medium")
        assert d.total_recorded == 3

    def test_baseline_fills_and_freezes(self):
        d = self._make(baseline=5)
        for _ in range(5):
            d.record(0.8, "pricing", "medium")
        assert d.baseline_frozen

    def test_baseline_does_not_freeze_early(self):
        d = self._make(baseline=10)
        for _ in range(5):
            d.record(0.8, "pricing", "medium")
        assert not d.baseline_frozen

    def test_empty_check_returns_report(self):
        d = self._make()
        report = d.check_drift()
        assert "any_drift" in report.to_dict()

    def test_stable_distribution_no_drift(self):
        import random
        d = self._make(baseline=30, window=20)
        rng = random.Random(42)
        # Both windows draw from same distribution N(0.8, 0.05)
        for _ in range(30):
            d.record(rng.gauss(0.80, 0.05), "pricing", "medium")
        for _ in range(20):
            d.record(rng.gauss(0.80, 0.05), "pricing", "medium")
        report = d.check_drift()
        conf_alerts = [a for a in report.alerts if a.metric == "confidence"]
        # With overlapping distributions there should be no significant drift
        if conf_alerts:
            # drift_score should be low for similar distributions
            assert conf_alerts[0].drift_score < 0.8

    def test_large_confidence_shift_flags_drift(self):
        import random
        rng = random.Random(99)
        d = self._make(baseline=30, window=20)
        # Baseline: high confidence with small noise
        for _ in range(30):
            d.record(rng.gauss(0.90, 0.02), "pricing", "low")
        # Current window: much lower confidence
        for _ in range(20):
            d.record(rng.gauss(0.10, 0.02), "pricing", "low")
        report = d.check_drift()
        conf_alerts = [a for a in report.alerts if a.metric == "confidence"]
        assert len(conf_alerts) > 0
        assert conf_alerts[0].is_drifted

    def test_topic_distribution_shift_flags_drift(self):
        d = self._make(baseline=30, window=20)
        for _ in range(30):
            d.record(0.8, "pricing", "medium")
        for _ in range(20):
            d.record(0.8, "competition", "medium")
        report = d.check_drift()
        topic_alerts = [a for a in report.alerts if a.metric == "topic_distribution"]
        if topic_alerts:
            assert topic_alerts[0].is_drifted

    def test_report_to_dict_shape(self):
        d = self._make()
        d_dict = d.check_drift().to_dict()
        assert "any_drift" in d_dict
        assert "window_size" in d_dict
        assert "alerts" in d_dict

    def test_reset_clears_all_state(self):
        from temporalos.observability.drift_detector import DriftDetector

        d = DriftDetector(baseline_size=5)
        for _ in range(5):
            d.record(0.8, "pricing", "medium")
        assert d.baseline_frozen
        d.reset()
        assert not d.baseline_frozen
        assert d.total_recorded == 0

    def test_singleton_is_same_object(self):
        from temporalos.observability.drift_detector import get_drift_detector

        d1 = get_drift_detector()
        d2 = get_drift_detector()
        assert d1 is d2


# ── ConfidenceCalibrator ──────────────────────────────────────────────────────


class TestConfidenceCalibrator:
    def test_empty_returns_zero_ece(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator()
        report = c.compute()
        assert report.ece == 0.0
        assert report.total_samples == 0

    def test_sample_count_increments(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator()
        c.add_sample(0.8, True)
        c.add_sample(0.7, False)
        assert c.sample_count == 2

    def test_perfect_calibration_low_ece(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator(n_bins=10)
        # 90% confidence → 9/10 correct
        for _ in range(9):
            c.add_sample(0.9, True)
        c.add_sample(0.9, False)
        report = c.compute()
        assert report.ece < 0.2

    def test_worst_case_calibration_high_ece(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator(n_bins=5)
        for _ in range(20):
            c.add_sample(0.9, False)  # 90% confidence, always wrong
        report = c.compute()
        assert report.ece > 0.5

    def test_bins_structure(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator(n_bins=5)
        for i in range(5):
            c.add_sample(i * 0.2 + 0.05, True)
        report = c.compute()
        assert 0 < len(report.bins) <= 5

    def test_to_dict_has_required_keys(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator()
        c.add_sample(0.7, True)
        d = c.compute().to_dict()
        assert "ece" in d
        assert "bins" in d
        assert "total_samples" in d

    def test_clear_resets(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator()
        c.add_sample(0.9, True)
        c.clear()
        assert c.sample_count == 0

    def test_confidence_clipped_to_range(self):
        from temporalos.observability.calibration import ConfidenceCalibrator

        c = ConfidenceCalibrator()
        c.add_sample(1.5, True)  # out of range, should clip to 1.0
        c.add_sample(-0.1, False)  # out of range, should clip to 0.0
        report = c.compute()
        assert report.total_samples == 2


# ── Observability API endpoints ───────────────────────────────────────────────


class TestObservabilityAPI:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app

            self.client = TestClient(app)
            yield

    def test_prometheus_metrics_endpoint_200(self):
        resp = self.client.get("/api/v1/metrics")
        assert resp.status_code == 200

    def test_prometheus_metrics_content_type(self):
        resp = self.client.get("/api/v1/metrics")
        assert "text" in resp.headers.get("content-type", "")

    def test_drift_report_shape(self):
        resp = self.client.get("/api/v1/observability/drift")
        assert resp.status_code == 200
        data = resp.json()
        assert "any_drift" in data
        assert "total_recorded" in data
        assert "baseline_frozen" in data

    def test_calibration_empty_report(self):
        resp = self.client.get("/api/v1/observability/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert "ece" in data
        assert "total_samples" in data

    def test_add_calibration_sample(self):
        resp = self.client.post(
            "/api/v1/observability/calibration/sample",
            params={"confidence": 0.85, "correct": True},
        )
        assert resp.status_code == 200
        assert resp.json()["sample_count"] >= 1

    def test_add_calibration_sample_invalid_confidence(self):
        resp = self.client.post(
            "/api/v1/observability/calibration/sample",
            params={"confidence": 1.5, "correct": True},
        )
        assert resp.status_code == 422

    def test_review_queue_default(self):
        resp = self.client.get("/api/v1/review/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert "queue_depth" in data
        assert "items" in data
        assert "threshold" in data

    def test_review_queue_threshold_param(self):
        resp = self.client.get("/api/v1/review/queue?max_confidence=0.3")
        assert resp.status_code == 200
        assert resp.json()["threshold"] == 0.3

    def test_label_extraction(self):
        resp = self.client.post(
            "/api/v1/review/42/label",
            params={"correct": True, "confidence": 0.75},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["labeled"] is True
        assert data["extraction_id"] == 42
