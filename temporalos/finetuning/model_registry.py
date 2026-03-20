"""
Model registry — Phase 4.

Tracks fine-tuning experiments: base model, LoRA config, training metrics,
adapter path, and evaluation scores. Persists to a JSON file on disk so
experiments survive restarts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LoRAConfig:
    base_model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"
    r: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    max_length: int = 1024

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LoRAConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TrainingMetrics:
    train_loss: float = 0.0
    val_loss: float = 0.0
    train_examples: int = 0
    val_examples: int = 0
    epochs_completed: int = 0
    total_steps: int = 0
    best_step: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingMetrics":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ExperimentRecord:
    """Immutable snapshot of one fine-tuning run."""

    id: str
    name: str
    status: str          # pending | running | completed | failed
    lora_config: LoRAConfig
    adapter_path: str = ""
    dataset_path: str = ""
    training_metrics: TrainingMetrics = field(default_factory=TrainingMetrics)
    eval_scores: dict = field(default_factory=dict)  # FieldScores.to_dict()
    created_at: str = ""
    completed_at: str = ""
    error: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["lora_config"] = self.lora_config.to_dict()
        d["training_metrics"] = self.training_metrics.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ExperimentRecord":
        lora = LoRAConfig.from_dict(d.pop("lora_config", {}))
        metrics = TrainingMetrics.from_dict(d.pop("training_metrics", {}))
        # filter extra keys from future schema migrations
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(lora_config=lora, training_metrics=metrics, **valid)

    @property
    def overall_f1(self) -> float:
        return float(self.eval_scores.get("overall_f1", 0.0))


class ModelRegistry:
    """
    File-backed store for LoRA fine-tuning experiments.

    Thread-safe for single-process use (no distributed locking).
    """

    def __init__(self, registry_file: str | Path = "/tmp/temporalos/finetuning/registry.json") -> None:
        self._path = Path(registry_file)
        self._records: dict[str, ExperimentRecord] = {}
        self._load()

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_experiment(
        self,
        name: str,
        lora_config: LoRAConfig,
        dataset_path: str = "",
        tags: list[str] | None = None,
    ) -> ExperimentRecord:
        """Register a new experiment (status=pending)."""
        record = ExperimentRecord(
            id=str(uuid.uuid4()),
            name=name,
            status="pending",
            lora_config=lora_config,
            dataset_path=dataset_path,
            created_at=datetime.utcnow().isoformat(),
            tags=tags or [],
        )
        self._records[record.id] = record
        self._save()
        return record

    def update(self, record: ExperimentRecord) -> None:
        """Persist changes to an existing record."""
        self._records[record.id] = record
        self._save()

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return self._records.get(experiment_id)

    def list_experiments(
        self,
        status: str | None = None,
        tag: str | None = None,
    ) -> list[ExperimentRecord]:
        records = list(self._records.values())
        if status:
            records = [r for r in records if r.status == status]
        if tag:
            records = [r for r in records if tag in r.tags]
        # newest first
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def best_by_metric(self, metric: str = "overall_f1") -> ExperimentRecord | None:
        """Return the completed experiment with the highest value for `metric`."""
        completed = [r for r in self._records.values() if r.status == "completed"]
        if not completed:
            return None
        return max(completed, key=lambda r: float(r.eval_scores.get(metric, 0.0)))

    def delete(self, experiment_id: str) -> bool:
        if experiment_id not in self._records:
            return False
        del self._records[experiment_id]
        self._save()
        return True

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for item in data.get("experiments", []):
                try:
                    rec = ExperimentRecord.from_dict(item)
                    self._records[rec.id] = rec
                except Exception:
                    pass  # skip corrupt records
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"experiments": [r.to_dict() for r in self._records.values()]}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._records)
