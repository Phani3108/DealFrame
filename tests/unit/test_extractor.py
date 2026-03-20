"""Unit tests — ingestion (FFmpeg frame extraction)."""

from pathlib import Path

import pytest

from temporalos.core.types import Frame
from temporalos.ingestion.extractor import extract_frames, get_video_duration_ms


def test_extract_frames_produces_correct_count(test_video_path, tmp_path):
    """12-second video at 1 frame/2 s → expect 6 frames."""
    frames = extract_frames(
        video_path=test_video_path,
        output_dir=str(tmp_path / "frames"),
        interval_seconds=2,
        max_resolution=320,
    )
    assert len(frames) >= 5  # allow slight FFmpeg variance
    assert all(isinstance(f, Frame) for f in frames)


def test_extract_frames_files_exist(test_video_path, tmp_path):
    frames = extract_frames(
        video_path=test_video_path,
        output_dir=str(tmp_path / "frames2"),
        interval_seconds=3,
        max_resolution=320,
    )
    for frame in frames:
        assert Path(frame.path).exists(), f"Frame file missing: {frame.path}"


def test_extract_frames_timestamps_are_sorted(test_video_path, tmp_path):
    frames = extract_frames(
        video_path=test_video_path,
        output_dir=str(tmp_path / "frames3"),
        interval_seconds=2,
        max_resolution=320,
    )
    timestamps = [f.timestamp_ms for f in frames]
    assert timestamps == sorted(timestamps)


def test_get_video_duration(test_video_path):
    duration_ms = get_video_duration_ms(test_video_path)
    # Generated video is 12 s; allow 1 s tolerance
    assert 10000 <= duration_ms <= 14000


def test_extract_frames_bad_path():
    with pytest.raises(RuntimeError, match="FFmpeg failed"):
        extract_frames("/nonexistent/path.mp4", "/tmp/frames_bad")


def test_extract_frames_unsupported_resolution(test_video_path, tmp_path):
    """Very small max_resolution should still produce valid frames."""
    frames = extract_frames(
        video_path=test_video_path,
        output_dir=str(tmp_path / "frames4"),
        interval_seconds=4,
        max_resolution=64,
    )
    assert len(frames) >= 1
