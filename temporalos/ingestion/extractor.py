"""FFmpeg-based video frame extraction."""

import json
import subprocess
from pathlib import Path

from ..core.types import Frame
from ..observability.telemetry import get_tracer


def extract_frames(
    video_path: str,
    output_dir: str,
    interval_seconds: int = 2,
    max_resolution: int = 1024,
) -> list[Frame]:
    """
    Extract one frame every `interval_seconds` from `video_path`.
    Frames are written as JPEG to `output_dir` and returned as a sorted list.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("ingestion.extract_frames") as span:
        span.set_attribute("video.path", video_path)
        span.set_attribute("video.frame_interval_seconds", interval_seconds)

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        scale_filter = (
            f"fps=1/{interval_seconds},"
            f"scale='if(gt(iw,ih),min({max_resolution},iw),-2)':"
            f"'if(gt(iw,ih),-2,min({max_resolution},ih))'"
        )

        result = subprocess.run(
            [
                "ffmpeg",
                "-i", video_path,
                "-vf", scale_filter,
                "-q:v", "2",
                str(out / "frame_%06d.jpg"),
                "-y",
                "-loglevel", "quiet",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr.strip()}")

        frame_files = sorted(out.glob("frame_*.jpg"))
        frames = [
            Frame(path=str(f), timestamp_ms=i * interval_seconds * 1000)
            for i, f in enumerate(frame_files)
        ]

        span.set_attribute("video.frames_extracted", len(frames))
        return frames


def get_video_duration_ms(video_path: str) -> int:
    """Return video duration in milliseconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    return int(float(data["format"]["duration"]) * 1000)
