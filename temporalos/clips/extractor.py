"""Clip extraction — cuts video at timestamp ranges using FFmpeg.

Clips are stored under TEMPORALOS_CLIPS_DIR/<job_id>/<clip_id>_<label>.mp4.
The ClipExtractor can also auto-identify the N most significant moments by
risk score, ready for one-click export.
"""
from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

CLIPS_DIR = Path(os.environ.get("TEMPORALOS_CLIPS_DIR", "/tmp/temporalos/clips"))


@dataclass
class ClipSpec:
    label: str
    start_ms: int
    end_ms: int
    risk_score: float = 0.0
    topic: str = ""

    def to_dict(self, clip_id: str = "") -> dict:
        s = self.start_ms
        return {
            "clip_id": clip_id,
            "label": self.label,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_s": round((self.end_ms - self.start_ms) / 1000, 1),
            "risk_score": self.risk_score,
            "topic": self.topic,
            "start_str": f"{s // 60000:02d}:{(s // 1000) % 60:02d}",
        }


@dataclass
class ExtractedClip:
    clip_id: str
    spec: ClipSpec
    path: Path
    size_bytes: int

    def to_dict(self) -> dict:
        return {
            **self.spec.to_dict(self.clip_id),
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "ready": self.path.exists(),
        }


class ClipExtractor:
    """Cuts video clips at timestamp ranges via FFmpeg."""

    def __init__(self, clips_dir: Path = CLIPS_DIR):
        self.clips_dir = clips_dir

    def _job_dir(self, job_id: str) -> Path:
        d = self.clips_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def extract(self, video_path: str, job_id: str, spec: ClipSpec) -> ExtractedClip:
        """Cut a clip from *video_path* covering [start_ms, end_ms]."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video not found: {video_path}")

        job_dir = self._job_dir(job_id)
        clip_id = uuid.uuid4().hex[:8]
        safe = spec.label.lower().replace(" ", "_")[:20]
        out_path = job_dir / f"{clip_id}_{safe}.mp4"

        start_s = spec.start_ms / 1000
        dur_s = (spec.end_ms - spec.start_ms) / 1000

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-i", video_path,
            "-t", str(dur_s),
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg clip extraction failed: {result.stderr.decode()[:300]}"
            )

        return ExtractedClip(
            clip_id=clip_id,
            spec=spec,
            path=out_path,
            size_bytes=out_path.stat().st_size,
        )

    def infer_significant_clips(
        self,
        segments: List[Dict[str, Any]],
        n: int = 5,
    ) -> List[ClipSpec]:
        """
        Auto-identify top-N most significant segments by risk_score.
        *segments* is a list of dicts from VideoIntelligence.to_dict()['segments'].
        """
        scored = sorted(segments,
                        key=lambda s: s.get("extraction", s).get("risk_score", 0),
                        reverse=True)
        clips: List[ClipSpec] = []
        for seg in scored[:n]:
            ext = seg.get("extraction", seg)
            ts_ms = seg.get("timestamp_ms", 0)
            clips.append(ClipSpec(
                label=f"{ext.get('topic', 'unknown')}_{ext.get('risk', 'low')}",
                start_ms=max(0, ts_ms - 5_000),
                end_ms=ts_ms + 20_000,
                risk_score=ext.get("risk_score", 0),
                topic=ext.get("topic", ""),
            ))
        return clips

    def list_clips(self, job_id: str) -> List[dict]:
        """List all previously extracted clips for a job."""
        job_dir = self._job_dir(job_id)
        result = []
        for f in sorted(job_dir.glob("*.mp4")):
            parts = f.stem.split("_", 1)
            result.append({
                "clip_id": parts[0],
                "label": parts[1] if len(parts) > 1 else "",
                "filename": f.name,
                "size_bytes": f.stat().st_size,
            })
        return result

    def get_clip_path(self, job_id: str, clip_id: str) -> Optional[Path]:
        job_dir = self._job_dir(job_id)
        for f in job_dir.glob(f"{clip_id}_*.mp4"):
            return f
        return None


_extractor: Optional[ClipExtractor] = None


def get_clip_extractor() -> ClipExtractor:
    global _extractor
    if _extractor is None:
        _extractor = ClipExtractor()
    return _extractor
