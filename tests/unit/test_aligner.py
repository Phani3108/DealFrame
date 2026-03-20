"""Unit tests — temporal alignment."""

from temporalos.alignment.aligner import align
from temporalos.core.types import Frame, Word


def _make_frames(timestamps_ms: list[int]) -> list[Frame]:
    return [Frame(path=f"/tmp/f_{t}.jpg", timestamp_ms=t) for t in timestamps_ms]


def _make_words(entries: list[tuple[str, int, int]]) -> list[Word]:
    return [Word(text=t, start_ms=s, end_ms=e) for t, s, e in entries]


def test_align_empty_inputs():
    assert align([], []) == []
    assert align([], _make_words([("hi", 0, 500)])) == []


def test_align_basic_window_assignment():
    frames = _make_frames([0, 2000, 4000])
    words = _make_words([
        ("hello", 100, 500),
        ("world", 2100, 2600),
        ("goodbye", 4200, 4800),
    ])
    segments = align(frames, words)
    assert len(segments) == 3
    assert segments[0].words[0].text == "hello"
    assert segments[1].words[0].text == "world"
    assert segments[2].words[0].text == "goodbye"


def test_align_word_at_exact_boundary():
    """Word starting exactly at a frame timestamp should belong to that frame."""
    frames = _make_frames([0, 2000])
    words = _make_words([("exact", 2000, 2500)])
    segments = align(frames, words)
    # word at 2000 ms belongs to the second frame window [2000, 2000+5000)
    assert segments[1].words[0].text == "exact"
    assert segments[0].words == []


def test_align_multiple_words_per_segment():
    frames = _make_frames([0, 5000])
    words = _make_words([
        ("a", 0, 300),
        ("b", 300, 700),
        ("c", 700, 1200),
        ("d", 5100, 5600),
    ])
    segments = align(frames, words)
    assert len(segments[0].words) == 3
    assert len(segments[1].words) == 1


def test_align_transcript_property():
    frames = _make_frames([0])
    words = _make_words([("the", 0, 300), ("price", 300, 700), ("is", 700, 900)])
    segments = align(frames, words)
    assert segments[0].transcript == "the price is"


def test_align_no_words_produces_empty_segments():
    frames = _make_frames([0, 2000, 4000])
    segments = align(frames, [])
    assert all(s.words == [] for s in segments)
    assert all(s.transcript == "" for s in segments)


def test_align_preserves_frame_count(sample_frames, sample_words):
    segments = align(sample_frames, sample_words)
    assert len(segments) == len(sample_frames)


def test_align_all_words_assigned(sample_frames, sample_words):
    """Every word must end up in exactly one segment."""
    segments = align(sample_frames, sample_words)
    assigned = [w for s in segments for w in s.words]
    assert len(assigned) == len(sample_words)
