"""
Fine-tuning API routes — Phase 4.

Exposes the full LoRA fine-tuning lifecycle over REST:
  POST /finetuning/dataset/export   — build dataset from DB extractions
  GET  /finetuning/dataset/stats    — count examples / class distribution
  POST /finetuning/train            — launch training job (background task)
  GET  /finetuning/runs             — list experiments
  GET  /finetuning/runs/{id}        — get run status + metrics
  POST /finetuning/runs/{id}/eval   — evaluate a trained adapter on a val set
  POST /finetuning/runs/{id}/activate — mark adapter as the active extraction model
  GET  /finetuning/runs/{id}/calibration — confidence calibration curve
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ...config import get_settings
from ...db.session import get_session
from ...finetuning.dataset_builder import DatasetBuilder, build_dataset_from_db
from ...finetuning.evaluator import ExtractionEvaluator
from ...finetuning.model_registry import ExperimentRecord, LoRAConfig, ModelRegistry, TrainingMetrics
from ...finetuning.trainer import LoRATrainer, TrainerConfig

router = APIRouter(prefix="/finetuning", tags=["finetuning"])

# ── In-memory training job state (production: move to DB or Celery) ───────────
_job_state: dict[str, dict] = {}


# ── Dataset endpoints ─────────────────────────────────────────────────────────

@router.post("/dataset/export", status_code=202)
async def export_dataset(
    background_tasks: BackgroundTasks,
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    train_ratio: float = Query(0.8, ge=0.5, le=0.99),
    session=Depends(get_session),
) -> dict:
    """
    Build a LoRA training dataset from all high-confidence DB extractions.
    Runs asynchronously. Returns a job_id to poll.
    """
    settings = get_settings()
    job_id = str(uuid.uuid4())
    _job_state[job_id] = {"status": "running", "type": "dataset_export"}

    async def _run():
        try:
            builder = await build_dataset_from_db(session, min_confidence=min_confidence)
            split = builder.split(train_ratio=train_ratio)

            dataset_dir = Path(settings.finetuning.dataset_dir) / job_id
            train_path = builder.to_jsonl(dataset_dir / "train.jsonl")

            # write val separately
            val_builder = DatasetBuilder()
            for ex in split.val:
                val_builder._examples.append(ex)
            val_path = val_builder.to_jsonl(dataset_dir / "val.jsonl")

            _job_state[job_id].update({
                "status": "completed",
                "total_examples": builder.size,
                "train_examples": len(split.train),
                "val_examples": len(split.val),
                "train_path": str(train_path),
                "val_path": str(val_path),
                "class_distribution": builder.class_distribution(),
            })
        except Exception as exc:
            _job_state[job_id].update({"status": "failed", "error": str(exc)})

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "running"}


@router.get("/dataset/stats")
async def dataset_stats(
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    session=Depends(get_session),
) -> dict:
    """Return dataset statistics without exporting to disk."""
    builder = await build_dataset_from_db(session, min_confidence=min_confidence)
    return {
        "total_examples": builder.size,
        "class_distribution": builder.class_distribution(),
    }


# ── Training endpoints ────────────────────────────────────────────────────────

@router.post("/train", status_code=202)
async def start_training(
    background_tasks: BackgroundTasks,
    name: str = Query(..., description="Human-readable experiment name"),
    train_path: str = Query(..., description="Path to training JSONL file"),
    val_path: str = Query(..., description="Path to validation JSONL file"),
    dry_run: bool = Query(False, description="Simulate training (for testing)"),
) -> dict:
    """
    Launch a LoRA fine-tuning job in the background.
    Returns an experiment_id to poll via GET /finetuning/runs/{id}.
    """
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    lora_cfg = LoRAConfig(
        base_model_id=settings.finetuning.base_model_id,
        r=settings.finetuning.lora_r,
        alpha=settings.finetuning.lora_alpha,
        dropout=settings.finetuning.lora_dropout,
        target_modules=settings.finetuning.target_modules,
        epochs=settings.finetuning.epochs,
        learning_rate=settings.finetuning.learning_rate,
        batch_size=settings.finetuning.batch_size,
        max_length=settings.finetuning.max_length,
    )

    record = registry.create_experiment(
        name=name, lora_config=lora_cfg, dataset_path=train_path
    )
    output_dir = str(Path(settings.finetuning.models_dir) / record.id)

    def _train():
        record.status = "running"
        registry.update(record)
        trainer_cfg = TrainerConfig.from_settings()
        result = LoRATrainer(trainer_cfg).train(
            train_path, val_path, output_dir,
            experiment_id=record.id, dry_run=dry_run,
        )
        if result.success:
            record.status = "completed"
            record.adapter_path = result.adapter_path
            record.training_metrics = TrainingMetrics(
                train_loss=result.train_loss,
                val_loss=result.val_loss,
                epochs_completed=result.epochs_completed,
                total_steps=result.total_steps,
            )
        else:
            record.status = "failed"
            record.error = result.error
        registry.update(record)

    background_tasks.add_task(_train)
    return {"experiment_id": record.id, "status": "running"}


@router.get("/runs")
async def list_runs(
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """List all fine-tuning experiments."""
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    runs = registry.list_experiments(status=status)
    return {
        "experiments": [r.to_dict() for r in runs],
        "total": len(runs),
    }


@router.get("/runs/{experiment_id}")
async def get_run(experiment_id: str) -> dict:
    """Get the status and metrics for a specific training run."""
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    record = registry.get(experiment_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")
    return record.to_dict()


@router.post("/runs/{experiment_id}/eval")
async def evaluate_run(
    experiment_id: str,
    val_path: str = Query(..., description="Path to validation JSONL"),
) -> dict:
    """
    Evaluate a completed fine-tuned adapter on a validation set.
    Stores eval_scores in the registry.
    """
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    record = registry.get(experiment_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")
    if record.status != "completed":
        raise HTTPException(status_code=409, detail="Experiment is not completed yet")
    if not Path(record.adapter_path).exists():
        raise HTTPException(status_code=409, detail="Adapter path not found on disk")

    # Load val set
    val_builder = DatasetBuilder.from_jsonl(val_path)
    split = val_builder.split(train_ratio=0.0)
    val_examples = val_builder._examples  # all examples used for eval

    from ...extraction.models.finetuned import FineTunedExtractionModel
    model = FineTunedExtractionModel(adapter_path=record.adapter_path)
    evaluator = ExtractionEvaluator()
    scores = evaluator.evaluate_model(model, val_examples)

    record.eval_scores = scores.to_dict()
    registry.update(record)

    return {"experiment_id": experiment_id, "eval_scores": scores.to_dict()}


@router.post("/runs/{experiment_id}/activate")
async def activate_run(experiment_id: str) -> dict:
    """Set a completed run's adapter as the active extraction model in settings."""
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    record = registry.get(experiment_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")
    if record.status != "completed":
        raise HTTPException(status_code=409, detail="Experiment is not completed yet")

    # In production this would write to .env or a config store.
    # For now, patch the in-process settings cache.
    settings.finetuning.adapter_path = record.adapter_path
    return {
        "activated": True,
        "experiment_id": experiment_id,
        "adapter_path": record.adapter_path,
    }


@router.get("/runs/{experiment_id}/calibration")
async def calibration_curve(
    experiment_id: str,
    val_path: str = Query(..., description="Path to validation JSONL"),
    n_bins: int = Query(5, ge=2, le=20),
) -> dict:
    """Compute confidence calibration curve for a trained model."""
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    record = registry.get(experiment_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")

    val_builder = DatasetBuilder.from_jsonl(val_path)
    val_examples = val_builder._examples

    from ...extraction.models.finetuned import FineTunedExtractionModel
    model = FineTunedExtractionModel(adapter_path=record.adapter_path)
    evaluator = ExtractionEvaluator()

    import json as _json
    pairs: list[tuple[dict, dict]] = []
    for ex in val_examples:
        from ...core.types import AlignedSegment, Frame, Word
        from ..finetuning.evaluator import _segment_from_input
        seg = _segment_from_input(ex.input)
        try:
            result = model.extract(seg)
            pred = {
                "confidence": result.confidence,
                "risk": result.risk,
            }
        except Exception:
            pred = {"confidence": 0.0, "risk": "low"}
        gt = _json.loads(ex.output)
        pairs.append((pred, gt))

    curve = evaluator.calibration_curve(pairs, n_bins=n_bins)
    return {"experiment_id": experiment_id, "calibration_curve": curve}


@router.get("/best")
async def best_model() -> dict:
    """Return the experiment with the highest eval overall_f1."""
    settings = get_settings()
    registry = ModelRegistry(settings.finetuning.registry_file)
    best = registry.best_by_metric("overall_f1")
    if not best:
        raise HTTPException(status_code=404, detail="No completed experiments found")
    return best.to_dict()
