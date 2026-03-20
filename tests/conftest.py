"""
Shared pytest fixtures for all test suites.

Key fixtures:
  - test_video_path     — generates a real 10-second MP4 using FFmpeg (no external assets)
  - sample_frames       — list[Frame] extracted from the test video
  - sample_words        — list[Word] with deterministic fake transcript
  - sample_segments     — list[AlignedSegment] aligned from frames + words
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from temporalos.alignment.aligner import align
from temporalos.core.types import AlignedSegment, Frame, Word
from temporalos.ingestion.extractor import extract_frames


# ── Synthetic video fixture ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory) -> str:
    """
    Create a 12-second test video using FFmpeg — no external files required.
    The video contains:
      - A blue colour field (simulates a slide screen)
      - A 440 Hz sine tone (simulates speech — Whisper will return near-empty transcript)
    """
    out_dir = tmp_path_factory.mktemp("test_video")
    video_path = str(out_dir / "test_call.mp4")

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            # 12-second 640×360 blue video at 24 fps
            "-i", "color=c=blue:size=640x360:rate=24:duration=12",
            # 12-second 440 Hz sine tone
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=12",
            "-c:v", "libx264",
            "-crf", "28",
            "-c:a", "aac",
            "-shortest",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"FFmpeg failed to create test video:\n{result.stderr}"
    return video_path


@pytest.fixture(scope="session")
def test_frames_dir(tmp_path_factory) -> str:
    return str(tmp_path_factory.mktemp("test_frames"))


@pytest.fixture(scope="session")
def sample_frames(test_video_path, test_frames_dir) -> list[Frame]:
    return extract_frames(
        video_path=test_video_path,
        output_dir=test_frames_dir,
        interval_seconds=2,
        max_resolution=320,  # small for speed
    )


@pytest.fixture()
def sample_words() -> list[Word]:
    """Deterministic fake transcript covering 12 seconds."""
    return [
        Word("So", 0, 400),
        Word("let's", 400, 900),
        Word("talk", 900, 1400),
        Word("about", 1400, 1900),
        Word("pricing", 1900, 2600),
        Word("the", 2600, 3000),
        Word("enterprise", 3000, 3800),
        Word("plan", 3800, 4400),
        Word("is", 4400, 4700),
        Word("four", 4700, 5100),
        Word("ninety", 5100, 5700),
        Word("nine", 5700, 6000),
        Word("a", 6000, 6200),
        Word("month", 6200, 7000),
        Word("that", 7000, 7300),
        Word("seems", 7300, 7800),
        Word("expensive", 7800, 8600),
        Word("compared", 8600, 9200),
        Word("to", 9200, 9400),
        Word("competitors", 9400, 10200),
        Word("can", 10200, 10500),
        Word("you", 10500, 10700),
        Word("send", 10700, 11100),
        Word("a", 11100, 11200),
        Word("proposal", 11200, 12000),
    ]


@pytest.fixture()
def sample_segments(sample_frames, sample_words) -> list[AlignedSegment]:
    return align(sample_frames, sample_words)
