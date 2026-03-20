"""Scene boundary detection using FFmpeg scene-change filter.

Primary: FFmpeg's `select=gt(scene,threshold)` filter via ffprobe
Fallback: uniform 5-second sampling when ffprobe is unavailable or detects nothing
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SceneBoundary:
    """Marks a detected scene transition in the video."""

    timestamp_ms: int
    frame_number: int
    score: float  # scene-change score that triggered the boundary


class SceneDetector:
    """
    Detects scene boundaries in a video file.

    Uses FFmpeg's built-in scene-change detection. Falls back to uniform
    5-second sampling if FFmpeg is unavailable or finds no transitions.
    """

    def __init__(
        self,
        threshold: float = 0.3,
        min_scene_duration_ms: int = 1000,
    ) -> None:
        self._threshold = threshold
        self._min_scene_ms = min_scene_duration_ms

    def detect(self, video_path: str) -> list[SceneBoundary]:
        """Detect scene boundaries in a video file. Raises FileNotFoundError if missing."""
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        return self._ffmpeg_detect(video_path)

    def _ffmpeg_detect(self, video_path: str) -> list[SceneBoundary]:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "packet=pts_time",
            "-select_streams", "v",
            "-print_format", "csv",
            "-f", "lavfi",
            f"movie={video_path},select=gt(scene\\,{self._threshold})",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            boundaries = self._parse_csv(result.stdout)
            if boundaries:
                return boundaries
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return self._uniform_fallback(video_path)

    def _parse_csv(self, stdout: str) -> list[SceneBoundary]:
        boundaries: list[SceneBoundary] = []
        last_ms = -self._min_scene_ms
        for line in stdout.splitlines():
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            try:
                pts_time = float(parts[-1])
                ts_ms = int(pts_time * 1000)
                if ts_ms - last_ms < self._min_scene_ms:
                    continue
                boundaries.append(
                    SceneBoundary(
                        timestamp_ms=ts_ms,
                        frame_number=len(boundaries),
                        score=self._threshold,
                    )
                )
                last_ms = ts_ms
            except (ValueError, IndexError):
                continue
        return boundaries

    def _uniform_fallback(self, video_path: str) -> list[SceneBoundary]:
        """Uniform 5-second pseudo-scene boundaries as a safe fallback."""
        duration_ms = self._get_duration_ms(video_path)
        interval_ms = 5000
        boundaries: list[SceneBoundary] = []
        ts = 0
        i = 0
        while ts < duration_ms:
            boundaries.append(SceneBoundary(timestamp_ms=ts, frame_number=i, score=0.0))
            ts += interval_ms
            i += 1
        return boundaries if boundaries else [SceneBoundary(0, 0, 0.0)]

    @staticmethod
    def _get_duration_ms(video_path: str) -> int:
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "csv",
                "-show_entries", "format=duration", video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            for line in result.stdout.splitlines():
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    return int(float(parts[-1]) * 1000)
        except Exception:
            pass
        return 30_000  # default 30s
