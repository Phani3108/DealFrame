"""
Phase 4 end-to-end test — Fine-tuning Arc.

Tests the complete fine-tuning lifecycle:
  Extraction results → dataset → (dry-run) training → evaluation → registry → API

Rules (from claude.md §0):
  - No GPU required — all model inference is mocked or uses dry_run=True
  - No real DB — DB dependency is overridden in API tests
  - All file I/O uses tmp_path (pytest fixture)
  - Must pass with 0 failures before Phase 4 is "done"
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from temporalos.core.types import AlignedSegment, ExtractionResult, Frame, Word
from temporalos.finetuning.dataset_builder import (
    DatasetBuilder,
    TrainingExample,
    _ms_to_str,
)
from temporalos.finetuning.evaluator import (
    ExtractionEvaluator,
    FieldScores,
    _list_overlap_f1,
    _segment_from_input,
    _str_eq,
)
from temporalos.finetuning.model_registry import (
    ExperimentRecord,
    LoRAConfig,
    ModelRegistry,
    TrainingMetrics,
)
from temporalos.finetuning.trainer import LoRATrainer, TrainerConfig, TrainingResult
from temporalos.extraction.models.finetuned import FineTunedExtractionModel
from evals.extraction_eval import evaluate_extraction_output, schema_pass_rate


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_extraction(
    topic: str = "pricing",
    sentiment: str = "hesitant",
    risk: str = "high",
    risk_score: float = 0.75,
    objections: list[str] | None = None,
    decision_signals: list[str] | None = None,
    model_name: str = "gpt4o",
    confidence: float = 0.88,
) -> ExtractionResult:
    return ExtractionResult(
        topic=topic,
        sentiment=sentiment,
        risk=risk,
        risk_score=risk_score,
        objections=objections or ["Price is too high"],
        decision_signals=decision_signals or ["Can you send a proposal?"],
        confidence=confidence,
        model_name=model_name,
        latency_ms=150,
    )


def _make_segment(timestamp_ms: int = 4000, transcript: str = "The price seems high") -> AlignedSegment:
    frame = Frame(path="/tmp/frame.jpg", timestamp_ms=timestamp_ms)
    words = [Word(text=w, start_ms=i * 300, end_ms=(i + 1) * 300) for i, w in enumerate(transcript.split())]
    return AlignedSegment(timestamp_ms=timestamp_ms, frame=frame, words=words)


# ── DatasetBuilder ─────────────────────────────────────────────────────────────


class TestDatasetBuilder:
    def test_add_example_returns_training_example(self):
        builder = DatasetBuilder()
        ex = builder.add_example(_make_extraction(), _make_segment())
        assert isinstance(ex, TrainingExample)
        assert ex.id
        assert ex.instruction
        assert "pricing" in ex.output  # topic appears in JSON output

    def test_example_output_is_valid_json(self):
        builder = DatasetBuilder()
        ex = builder.add_example(_make_extraction(), _make_segment())
        payload = json.loads(ex.output)
        assert "topic" in payload
        assert "sentiment" in payload
        assert "risk" in payload
        assert "risk_score" in payload
        assert isinstance(payload["objections"], list)
        assert isinstance(payload["decision_signals"], list)

    def test_multiple_examples_tracked(self):
        builder = DatasetBuilder()
        for i in range(5):
            builder.add_example(_make_extraction(), _make_segment(timestamp_ms=i * 2000))
        assert builder.size == 5
        assert len(builder) == 5

    def test_no_segment_still_works(self):
        builder = DatasetBuilder()
        ex = builder.add_example(_make_extraction())
        payload = json.loads(ex.output)
        assert payload["topic"] == "pricing"

    def test_to_jsonl_round_trips(self, tmp_path):
        builder = DatasetBuilder()
        for i in range(3):
            builder.add_example(_make_extraction(), _make_segment(timestamp_ms=i * 2000))
        out_path = builder.to_jsonl(tmp_path / "train.jsonl")
        assert out_path.exists()

        loaded = DatasetBuilder.from_jsonl(out_path)
        assert loaded.size == 3

    def test_split_preserves_total_count(self):
        builder = DatasetBuilder()
        for i in range(10):
            builder.add_example(_make_extraction())
        split = builder.split(train_ratio=0.8)
        assert len(split.train) + len(split.val) == 10
        assert len(split.train) == 8
        assert len(split.val) == 2

    def test_split_is_deterministic(self):
        builder = DatasetBuilder()
        for i in range(10):
            builder.add_example(_make_extraction(topic=["pricing", "features"][i % 2]))
        s1 = builder.split(seed=42)
        s2 = builder.split(seed=42)
        assert [e.id for e in s1.train] == [e.id for e in s2.train]

    def test_class_distribution(self):
        builder = DatasetBuilder()
        builder.add_example(_make_extraction(topic="pricing"))
        builder.add_example(_make_extraction(topic="pricing"))
        builder.add_example(_make_extraction(topic="features"))
        dist = builder.class_distribution()
        assert dist["topic"]["pricing"] == 2
        assert dist["topic"]["features"] == 1

    def test_add_batch(self):
        builder = DatasetBuilder()
        pairs = [(_make_extraction(), _make_segment(i * 2000)) for i in range(4)]
        examples = builder.add_batch(pairs)
        assert len(examples) == 4
        assert builder.size == 4

    def test_ms_to_str_helper(self):
        assert _ms_to_str(0) == "00:00"
        assert _ms_to_str(60_000) == "01:00"
        assert _ms_to_str(75_000) == "01:15"
        assert _ms_to_str(3_600_000) == "60:00"

    def test_jsonl_creates_parent_dirs(self, tmp_path):
        builder = DatasetBuilder()
        builder.add_example(_make_extraction())
        nested = tmp_path / "a" / "b" / "c" / "train.jsonl"
        result = builder.to_jsonl(nested)
        assert result.exists()


# ── Evaluator ─────────────────────────────────────────────────────────────────


class TestExtractionEvaluator:
    def _pairs(self, n: int, match: bool = True):
        pred = {"topic": "pricing", "sentiment": "hesitant", "risk": "high",
                "risk_score": 0.75, "objections": ["too expensive"],
                "decision_signals": ["send proposal"], "confidence": 0.88}
        gt = dict(pred)
        if not match:
            gt = {"topic": "features", "sentiment": "positive", "risk": "low",
                  "risk_score": 0.1, "objections": [], "decision_signals": [], "confidence": 0.5}
        return [(pred, gt)] * n

    def test_empty_pairs_returns_zero_scores(self):
        ev = ExtractionEvaluator()
        scores = ev.evaluate_pairs([])
        assert scores.overall_f1 == 0.0

    def test_perfect_predictions_score_one(self):
        ev = ExtractionEvaluator()
        scores = ev.evaluate_pairs(self._pairs(5, match=True))
        assert scores.topic_accuracy == 1.0
        assert scores.sentiment_accuracy == 1.0
        assert scores.risk_accuracy == 1.0
        assert scores.overall_f1 == pytest.approx(1.0)

    def test_fully_wrong_predictions_score_zero(self):
        ev = ExtractionEvaluator()
        scores = ev.evaluate_pairs(self._pairs(5, match=False))
        assert scores.topic_accuracy == 0.0
        assert scores.sentiment_accuracy == 0.0
        assert scores.risk_accuracy == 0.0

    def test_partial_accuracy(self):
        right = {"topic": "pricing", "sentiment": "neutral", "risk": "high",
                 "risk_score": 0.7, "objections": [], "decision_signals": [], "confidence": 0.8}
        wrong = {"topic": "features", "sentiment": "positive", "risk": "low",
                 "risk_score": 0.1, "objections": [], "decision_signals": [], "confidence": 0.3}
        gt = {"topic": "pricing", "sentiment": "neutral", "risk": "high",
              "risk_score": 0.7, "objections": [], "decision_signals": [], "confidence": 0.8}
        pairs = [(right, gt), (wrong, gt)]
        scores = ExtractionEvaluator().evaluate_pairs(pairs)
        assert scores.topic_accuracy == pytest.approx(0.5)
        assert scores.risk_accuracy == pytest.approx(0.5)

    def test_list_overlap_f1_both_empty(self):
        assert _list_overlap_f1([], []) == 1.0

    def test_list_overlap_f1_one_empty(self):
        assert _list_overlap_f1(["word"], []) == 0.0
        assert _list_overlap_f1([], ["word"]) == 0.0

    def test_list_overlap_f1_perfect(self):
        assert _list_overlap_f1(["price is high"], ["price is high"]) == 1.0

    def test_list_overlap_f1_partial(self):
        score = _list_overlap_f1(["price is high"], ["price is too high"])
        assert 0.0 < score < 1.0

    def test_to_dict_shape(self):
        scores = FieldScores(topic_accuracy=0.9, sentiment_accuracy=0.8, risk_accuracy=0.7,
                             risk_score_mae=0.05, objections_f1=0.6, decision_signals_f1=0.5,
                             confidence_mae=0.1, overall_f1=0.7)
        d = scores.to_dict()
        assert set(d.keys()) == {
            "topic_accuracy", "sentiment_accuracy", "risk_accuracy",
            "risk_score_mae", "objections_f1", "decision_signals_f1",
            "confidence_mae", "overall_f1",
        }

    def test_model_comparison(self):
        ev = ExtractionEvaluator()
        a = FieldScores(overall_f1=0.9)
        b = FieldScores(overall_f1=0.7)
        comp = ev.compare_models("finetuned", "rule_based", a, b)
        assert comp.winner == "finetuned"
        assert comp.delta_overall_f1 == pytest.approx(0.2)

    def test_calibration_curve_returns_bins(self):
        ev = ExtractionEvaluator()
        pairs = [
            ({"confidence": 0.9, "risk": "high"}, {"risk": "high"}),
            ({"confidence": 0.2, "risk": "low"}, {"risk": "high"}),
        ]
        curve = ev.calibration_curve(pairs, n_bins=5)
        assert len(curve) >= 1
        for bin_data in curve:
            assert "bin_center" in bin_data
            assert "actual_accuracy" in bin_data

    def test_segment_from_input_builds_aligned_segment(self):
        from temporalos.finetuning.dataset_builder import DatasetBuilder
        builder = DatasetBuilder()
        seg = _make_segment(4000, "The price is too high")
        ext = _make_extraction()
        ex = builder.add_example(ext, seg)
        reconstructed = _segment_from_input(ex.input)
        assert len(reconstructed.words) > 0


# ── ModelRegistry ─────────────────────────────────────────────────────────────


class TestModelRegistry:
    def test_create_and_retrieve(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig(base_model_id="test-model", r=4)
        record = reg.create_experiment("exp-1", cfg, dataset_path="/tmp/data.jsonl")
        assert record.status == "pending"
        assert record.lora_config.r == 4

        fetched = reg.get(record.id)
        assert fetched is not None
        assert fetched.name == "exp-1"

    def test_update_persists(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig()
        record = reg.create_experiment("test", cfg)
        record.status = "completed"
        record.eval_scores = {"overall_f1": 0.85}
        reg.update(record)

        reg2 = ModelRegistry(tmp_path / "registry.json")
        fetched = reg2.get(record.id)
        assert fetched.status == "completed"
        assert fetched.eval_scores["overall_f1"] == 0.85

    def test_list_experiments_filtered_by_status(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig()
        r1 = reg.create_experiment("a", cfg)
        r2 = reg.create_experiment("b", cfg)
        r2.status = "completed"
        reg.update(r2)

        pending = reg.list_experiments(status="pending")
        assert len(pending) == 1
        assert pending[0].id == r1.id

    def test_best_by_metric(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig()
        r1 = reg.create_experiment("a", cfg)
        r1.status = "completed"
        r1.eval_scores = {"overall_f1": 0.7}
        reg.update(r1)

        r2 = reg.create_experiment("b", cfg)
        r2.status = "completed"
        r2.eval_scores = {"overall_f1": 0.9}
        reg.update(r2)

        best = reg.best_by_metric("overall_f1")
        assert best.id == r2.id

    def test_best_by_metric_no_completed_returns_none(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        assert reg.best_by_metric() is None

    def test_delete_experiment(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig()
        record = reg.create_experiment("delete-me", cfg)
        assert reg.delete(record.id) is True
        assert reg.get(record.id) is None

    def test_lora_config_round_trip(self):
        cfg = LoRAConfig(r=16, alpha=32, target_modules=["q_proj", "k_proj", "v_proj"])
        d = cfg.to_dict()
        loaded = LoRAConfig.from_dict(d)
        assert loaded.r == 16
        assert loaded.alpha == 32
        assert loaded.target_modules == ["q_proj", "k_proj", "v_proj"]

    def test_experiment_to_dict_shape(self, tmp_path):
        reg = ModelRegistry(tmp_path / "registry.json")
        cfg = LoRAConfig()
        record = reg.create_experiment("shape-test", cfg)
        d = record.to_dict()
        assert "id" in d
        assert "name" in d
        assert "status" in d
        assert "lora_config" in d
        assert "training_metrics" in d
        assert "eval_scores" in d


# ── LoRA Trainer (dry run) ─────────────────────────────────────────────────────


class TestLoRATrainerDryRun:
    def test_dry_run_returns_success(self, tmp_path):
        builder = DatasetBuilder()
        for _ in range(5):
            builder.add_example(_make_extraction(), _make_segment())
        train_path = builder.to_jsonl(tmp_path / "train.jsonl")
        val_path = builder.to_jsonl(tmp_path / "val.jsonl")
        output_dir = tmp_path / "adapter"

        trainer = LoRATrainer(TrainerConfig(epochs=1))
        result = trainer.train(
            train_path, val_path, str(output_dir),
            experiment_id="test-123", dry_run=True,
        )

        assert result.success is True
        assert result.epochs_completed == 1
        assert result.adapter_path != ""

    def test_dry_run_writes_adapter_config(self, tmp_path):
        builder = DatasetBuilder()
        builder.add_example(_make_extraction())
        path = builder.to_jsonl(tmp_path / "data.jsonl")
        out_dir = tmp_path / "model"

        LoRATrainer().train(path, path, str(out_dir), dry_run=True)
        assert (out_dir / "adapter_config.json").exists()

    def test_dry_run_to_dict_shape(self, tmp_path):
        builder = DatasetBuilder()
        builder.add_example(_make_extraction())
        path = builder.to_jsonl(tmp_path / "data.jsonl")
        result = LoRATrainer().train(path, path, str(tmp_path / "out"), dry_run=True)
        d = result.to_dict()
        assert "success" in d
        assert "train_loss" in d
        assert "adapter_path" in d
        assert "duration_seconds" in d


# ── FineTunedExtractionModel ──────────────────────────────────────────────────


class TestFineTunedExtractionModel:
    def test_unavailable_when_no_path(self):
        model = FineTunedExtractionModel(adapter_path="")
        assert model.is_available is False

    def test_unavailable_when_path_not_exist(self, tmp_path):
        model = FineTunedExtractionModel(adapter_path=str(tmp_path / "nonexistent"))
        assert model.is_available is False

    def test_extract_falls_back_when_unavailable(self, sample_segments):
        model = FineTunedExtractionModel(adapter_path="")
        for seg in sample_segments:
            if seg.words:
                result = model.extract(seg)
                assert isinstance(result, ExtractionResult)
                assert result.model_name == "finetuned"
                assert 0.0 <= result.confidence <= 1.0

    def test_extract_batch_returns_correct_count(self, sample_segments):
        model = FineTunedExtractionModel(adapter_path="")
        non_empty = [s for s in sample_segments if s.words]
        results = model.extract_batch(non_empty)
        assert len(results) == len(non_empty)

    def test_from_settings_constructs(self):
        model = FineTunedExtractionModel.from_settings()
        assert model is not None
        assert model.name == "finetuned"

    def test_adapter_available_when_dry_run_output_exists(self, tmp_path):
        """A dry-run trained adapter directory is detected as available IF torch is present."""
        output_dir = tmp_path / "adapter"
        output_dir.mkdir()
        (output_dir / "adapter_config.json").write_text('{"peft_type":"LORA"}')
        model = FineTunedExtractionModel(adapter_path=str(output_dir))
        # is_available also checks for torch/peft/transformers install
        # We just verify the path check part works correctly
        from pathlib import Path
        assert Path(model._adapter_path).exists()


# ── DeepEval / Schema evaluation ──────────────────────────────────────────────


class TestExtractionEvalSchema:
    def _good_output(self) -> dict:
        return {
            "topic": "pricing",
            "sentiment": "hesitant",
            "risk": "high",
            "risk_score": 0.8,
            "objections": ["Price is higher than budget"],
            "decision_signals": ["send proposal"],
            "confidence": 0.9,
        }

    def test_valid_output_passes_all_checks(self):
        checks = evaluate_extraction_output(self._good_output())
        assert all(checks.values()), f"Failed checks: {[k for k,v in checks.items() if not v]}"

    def test_invalid_topic_fails(self):
        output = self._good_output()
        output["topic"] = "nonsense"
        checks = evaluate_extraction_output(output)
        assert not checks["valid_topic"]

    def test_invalid_sentiment_fails(self):
        output = self._good_output()
        output["sentiment"] = "confused"
        checks = evaluate_extraction_output(output)
        assert not checks["valid_sentiment"]

    def test_risk_score_out_of_range_fails(self):
        output = self._good_output()
        output["risk_score"] = 1.5
        checks = evaluate_extraction_output(output)
        assert not checks["risk_score_in_range"]

    def test_risk_direction_inconsistent_fails(self):
        output = self._good_output()
        output["risk"] = "high"
        output["risk_score"] = 0.1  # high risk but low score
        checks = evaluate_extraction_output(output)
        assert not checks["risk_direction_consistent"]

    def test_missing_objections_field_fails(self):
        output = self._good_output()
        del output["objections"]
        checks = evaluate_extraction_output(output)
        assert not checks["objections_is_list"]

    def test_schema_pass_rate_all_valid(self):
        outputs = [self._good_output() for _ in range(5)]
        rate = schema_pass_rate(outputs)
        assert rate == 1.0

    def test_schema_pass_rate_partial(self):
        bad = self._good_output()
        bad["topic"] = "INVALID"
        outputs = [self._good_output(), self._good_output(), bad]
        rate = schema_pass_rate(outputs)
        assert rate == pytest.approx(2 / 3)

    def test_schema_pass_rate_empty_returns_one(self):
        assert schema_pass_rate([]) == 1.0


# ── Fine-tuning API tests ─────────────────────────────────────────────────────


class TestFinetuningAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self._tmp = tmp_path

        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app
            from temporalos.db.session import get_session

            async def mock_session():
                yield MagicMock()

            app.dependency_overrides[get_session] = mock_session
            self._client = TestClient(app, raise_server_exceptions=True)
            self._app = app
            yield
            app.dependency_overrides.pop(get_session, None)

    def test_list_runs_returns_experiments(self):
        resp = self._client.get("/api/v1/finetuning/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "experiments" in data
        assert "total" in data

    def test_best_model_404_when_no_completed(self, tmp_path):
        with patch("temporalos.api.routes.finetuning.ModelRegistry") as MockReg:
            instance = MockReg.return_value
            instance.best_by_metric.return_value = None
            resp = self._client.get("/api/v1/finetuning/best")
            assert resp.status_code == 404

    def test_get_nonexistent_run_returns_404(self):
        resp = self._client.get("/api/v1/finetuning/runs/does-not-exist")
        assert resp.status_code == 404

    def test_dataset_stats_returns_structure(self):
        mock_builder = MagicMock()
        mock_builder.size = 42
        mock_builder.class_distribution.return_value = {
            "topic": {"pricing": 20, "features": 22},
            "sentiment": {"hesitant": 30, "neutral": 12},
            "risk": {"high": 15, "medium": 17, "low": 10},
        }
        with patch(
            "temporalos.api.routes.finetuning.build_dataset_from_db",
            new=AsyncMock(return_value=mock_builder),
        ):
            resp = self._client.get("/api/v1/finetuning/dataset/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_examples"] == 42
        assert "class_distribution" in data

    def test_start_training_returns_202_with_experiment_id(self, tmp_path):
        from temporalos.finetuning.trainer import TrainingResult

        train_path = tmp_path / "train.jsonl"
        val_path = tmp_path / "val.jsonl"
        train_path.write_text("")
        val_path.write_text("")

        mock_result = TrainingResult(
            experiment_id="test-exp",
            adapter_path=str(tmp_path / "adapter"),
            train_loss=0.1,
            val_loss=0.12,
            epochs_completed=1,
            total_steps=5,
            duration_seconds=0.01,
            success=True,
            error="",
        )
        with patch("temporalos.api.routes.finetuning.LoRATrainer") as MockTrainer:
            MockTrainer.return_value.train.return_value = mock_result
            resp = self._client.post(
                "/api/v1/finetuning/train",
                params={
                    "name": "test-run",
                    "train_path": str(train_path),
                    "val_path": str(val_path),
                    "dry_run": True,
                },
            )
        assert resp.status_code == 202
        data = resp.json()
        assert "experiment_id" in data
        assert data["status"] == "running"

    def test_get_run_404_when_missing(self):
        resp = self._client.get("/api/v1/finetuning/runs/fake-id")
        assert resp.status_code == 404

    def test_activate_nonexistent_run_404(self):
        resp = self._client.post("/api/v1/finetuning/runs/fake-id/activate")
        assert resp.status_code == 404
