"""
Extraction quality evaluator — Phase 4.

Computes field-level accuracy and item-overlap F1 for structured extraction
predictions vs. ground-truth labels. Designed for:
  1. Evaluating a fine-tuned model on a held-out validation set
  2. Comparing two extraction models (e.g. fine-tuned vs. GPT-4o)
  3. Tracking accuracy over time (drift detection)

All evaluation logic is pure-Python — no GPU, no API calls, no DB needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FieldScores:
    """Per-field accuracy / F1 for one evaluation run."""

    topic_accuracy: float = 0.0
    sentiment_accuracy: float = 0.0
    risk_accuracy: float = 0.0
    risk_score_mae: float = 0.0        # mean absolute error (0–1)
    objections_f1: float = 0.0
    decision_signals_f1: float = 0.0
    confidence_mae: float = 0.0
    overall_f1: float = 0.0             # macro-average of class accuracies

    def to_dict(self) -> dict:
        return {
            "topic_accuracy": round(self.topic_accuracy, 4),
            "sentiment_accuracy": round(self.sentiment_accuracy, 4),
            "risk_accuracy": round(self.risk_accuracy, 4),
            "risk_score_mae": round(self.risk_score_mae, 4),
            "objections_f1": round(self.objections_f1, 4),
            "decision_signals_f1": round(self.decision_signals_f1, 4),
            "confidence_mae": round(self.confidence_mae, 4),
            "overall_f1": round(self.overall_f1, 4),
        }


@dataclass
class ModelComparison:
    """Side-by-side evaluation of two models on the same validation set."""

    model_a: str
    model_b: str
    scores_a: FieldScores
    scores_b: FieldScores
    winner: str = ""              # model with higher overall_f1
    delta_overall_f1: float = 0.0

    def to_dict(self) -> dict:
        return {
            "model_a": self.model_a,
            "model_b": self.model_b,
            "scores_a": self.scores_a.to_dict(),
            "scores_b": self.scores_b.to_dict(),
            "winner": self.winner,
            "delta_overall_f1": round(self.delta_overall_f1, 4),
        }


# ── Core evaluator ────────────────────────────────────────────────────────────

class ExtractionEvaluator:
    """
    Evaluate structured extraction quality by comparing prediction dicts
    against ground-truth dicts.

    Supports two input modes:
      1. evaluate_pairs(pred_gt_pairs) — takes [(pred_dict, gt_dict), ...]
      2. evaluate_model(model, examples) — runs model.extract() on each example
         and compares against the stored output field
    """

    # ── pair-based evaluation (pure Python, no model needed) ─────────────────

    def evaluate_pairs(
        self, pairs: list[tuple[dict, dict]]
    ) -> FieldScores:
        """
        Evaluate a list of (prediction, ground_truth) dict pairs.

        Each dict must have keys: topic, sentiment, risk, risk_score,
        objections, decision_signals, confidence.
        """
        if not pairs:
            return FieldScores()

        topic_correct = 0
        sentiment_correct = 0
        risk_correct = 0
        risk_score_abs_errors: list[float] = []
        conf_abs_errors: list[float] = []
        obj_f1_scores: list[float] = []
        ds_f1_scores: list[float] = []

        for pred, gt in pairs:
            topic_correct += int(_str_eq(pred.get("topic"), gt.get("topic")))
            sentiment_correct += int(_str_eq(pred.get("sentiment"), gt.get("sentiment")))
            risk_correct += int(_str_eq(pred.get("risk"), gt.get("risk")))

            risk_score_abs_errors.append(
                abs(float(pred.get("risk_score", 0)) - float(gt.get("risk_score", 0)))
            )
            conf_abs_errors.append(
                abs(float(pred.get("confidence", 0)) - float(gt.get("confidence", 0)))
            )

            obj_f1_scores.append(
                _list_overlap_f1(pred.get("objections") or [], gt.get("objections") or [])
            )
            ds_f1_scores.append(
                _list_overlap_f1(
                    pred.get("decision_signals") or [],
                    gt.get("decision_signals") or [],
                )
            )

        n = len(pairs)
        topic_acc = topic_correct / n
        sentiment_acc = sentiment_correct / n
        risk_acc = risk_correct / n
        obj_f1 = sum(obj_f1_scores) / n
        ds_f1 = sum(ds_f1_scores) / n
        overall = (topic_acc + sentiment_acc + risk_acc + obj_f1 + ds_f1) / 5

        return FieldScores(
            topic_accuracy=topic_acc,
            sentiment_accuracy=sentiment_acc,
            risk_accuracy=risk_acc,
            risk_score_mae=sum(risk_score_abs_errors) / n,
            objections_f1=obj_f1,
            decision_signals_f1=ds_f1,
            confidence_mae=sum(conf_abs_errors) / n,
            overall_f1=overall,
        )

    def evaluate_model(
        self,
        model: Any,
        examples: list[Any],  # list of TrainingExample
    ) -> FieldScores:
        """
        Run model.extract() on each TrainingExample's segment (reconstructed
        from the input field) and compare against the stored output.
        """
        from .dataset_builder import TrainingExample

        from ..core.types import AlignedSegment, Word

        pairs: list[tuple[dict, dict]] = []
        for ex in examples:
            gt = json.loads(ex.output)
            # Build a minimal AlignedSegment from the input text
            seg = _segment_from_input(ex.input)
            try:
                result = model.extract(seg)
                pred = {
                    "topic": result.topic,
                    "sentiment": result.sentiment,
                    "risk": result.risk,
                    "risk_score": result.risk_score,
                    "objections": result.objections,
                    "decision_signals": result.decision_signals,
                    "confidence": result.confidence,
                }
            except Exception:
                # model failed — score 0 for this example
                pred = {}
            pairs.append((pred, gt))
        return self.evaluate_pairs(pairs)

    # ── model comparison ──────────────────────────────────────────────────────

    def compare_models(
        self,
        model_a_name: str,
        model_b_name: str,
        scores_a: FieldScores,
        scores_b: FieldScores,
    ) -> ModelComparison:
        delta = scores_a.overall_f1 - scores_b.overall_f1
        winner = model_a_name if delta >= 0 else model_b_name
        return ModelComparison(
            model_a=model_a_name,
            model_b=model_b_name,
            scores_a=scores_a,
            scores_b=scores_b,
            winner=winner,
            delta_overall_f1=delta,
        )

    # ── confidence calibration ────────────────────────────────────────────────

    def calibration_curve(
        self, pairs: list[tuple[dict, dict]], n_bins: int = 5
    ) -> list[dict]:
        """
        Compute 'predicted confidence vs actual accuracy' calibration buckets.
        Returns a list of {confidence_bin_center, predicted_confidence, actual_accuracy, count}.
        """
        if not pairs:
            return []

        bin_width = 1.0 / n_bins
        bins: dict[int, list[tuple[float, bool]]] = {i: [] for i in range(n_bins)}

        for pred, gt in pairs:
            conf = float(pred.get("confidence", 0.0))
            correct = _str_eq(pred.get("risk"), gt.get("risk"))
            bin_idx = min(int(conf / bin_width), n_bins - 1)
            bins[bin_idx].append((conf, correct))

        results = []
        for i, items in bins.items():
            if not items:
                continue
            center = (i + 0.5) * bin_width
            avg_conf = sum(c for c, _ in items) / len(items)
            accuracy = sum(1 for _, ok in items if ok) / len(items)
            results.append({
                "bin_center": round(center, 2),
                "avg_predicted_confidence": round(avg_conf, 4),
                "actual_accuracy": round(accuracy, 4),
                "count": len(items),
            })
        return results


# ── Pure-Python helpers ────────────────────────────────────────────────────────

def _str_eq(a: Any, b: Any) -> bool:
    return str(a or "").lower().strip() == str(b or "").lower().strip()


def _list_overlap_f1(pred: list[str], gt: list[str]) -> float:
    """
    Compute token-level F1 between two lists of strings.
    Each string is tokenised by whitespace. Handles empty lists gracefully.
    """
    if not pred and not gt:
        return 1.0  # both predicted empty and ground truth empty → correct
    if not pred or not gt:
        return 0.0

    pred_tokens = set(" ".join(pred).lower().split())
    gt_tokens = set(" ".join(gt).lower().split())

    if not gt_tokens:
        return 1.0 if not pred_tokens else 0.0

    overlap = pred_tokens & gt_tokens
    if not overlap:
        return 0.0

    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gt_tokens)
    return 2 * precision * recall / (precision + recall)


def _segment_from_input(input_text: str) -> Any:
    """
    Reconstruct a minimal AlignedSegment from the input text produced by
    DatasetBuilder so evaluate_model() can call model.extract(segment).
    """
    from ..core.types import AlignedSegment, Frame, Word

    lines = input_text.strip().splitlines()
    transcript = ""
    for i, line in enumerate(lines):
        if line.startswith("Transcript:"):
            # collect lines until the next blank or "Visual context:"
            transcript_lines = []
            for subsequent in lines[i + 1:]:
                if subsequent.startswith("Visual context:") or subsequent == "":
                    break
                transcript_lines.append(subsequent)
            transcript = " ".join(transcript_lines)
            break

    words = [
        Word(text=w, start_ms=0, end_ms=500)
        for w in transcript.split()
        if w
    ]
    frame = Frame(path="", timestamp_ms=0)
    return AlignedSegment(timestamp_ms=0, frame=frame, words=words)
