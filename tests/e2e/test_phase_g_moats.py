"""End-to-end tests for Phase G — Competitive Moats."""
import pytest

# ---------------------------------------------------------------------------
# G1  Temporal Diff Engine
# ---------------------------------------------------------------------------
from temporalos.intelligence.diff_engine import diff_calls, DiffResult


class TestDiffEngine:
    def test_diff_calls_basic(self):
        intel_a = {
            "overall_risk_score": 0.3,
            "segments": [
                {"extraction": {"topic": "pricing", "sentiment": "neutral",
                                "risk_score": 0.3, "objections": ["too expensive"],
                                "decision_signals": []}}
            ]
        }
        intel_b = {
            "overall_risk_score": 0.1,
            "segments": [
                {"extraction": {"topic": "pricing", "sentiment": "positive",
                                "risk_score": 0.1, "objections": [],
                                "decision_signals": ["send contract"]}}
            ]
        }
        result = diff_calls("call_a", intel_a, "call_b", intel_b)
        assert isinstance(result, DiffResult)
        assert "too expensive" in result.resolved_objections
        assert "send contract" in result.new_signals
        assert result.risk_delta < 0  # risk went down

    def test_diff_empty_calls(self):
        result = diff_calls("a", {"segments": []}, "b", {"segments": []})
        assert result.risk_delta == 0.0

    def test_diff_summary_generated(self):
        intel_a = {"segments": [{"extraction": {"topic": "demo", "sentiment": "negative",
                    "risk_score": 0.8, "objections": ["no budget"],
                    "decision_signals": []}}]}
        intel_b = {"segments": [{"extraction": {"topic": "demo", "sentiment": "positive",
                    "risk_score": 0.2, "objections": [],
                    "decision_signals": ["next steps"]}}]}
        result = diff_calls("a", intel_a, "b", intel_b)
        assert result.summary  # non-empty string


# ---------------------------------------------------------------------------
# G2  Franchise Mode
# ---------------------------------------------------------------------------
from temporalos.intelligence.franchise import classify_vertical, auto_classify_and_extract


class TestFranchise:
    def test_classify_sales(self):
        intel = {"segments": [
            {"extraction": {"topic": "pricing discussion", "objections": ["budget concern"],
                            "decision_signals": ["send proposal"]}},
            {"extraction": {"topic": "deal review", "objections": [],
                            "decision_signals": ["close deal"]}},
        ]}
        vertical, conf, _ = classify_vertical(intel)
        assert vertical == "sales_call"
        assert conf > 0

    def test_classify_ux(self):
        intel = {"segments": [
            {"extraction": {"topic": "usability user experience prototype", "objections": [],
                            "decision_signals": []},
             "transcript": "Let's do a usability test with the wireframe prototype and navigation"},
            {"extraction": {"topic": "user test think aloud pain point", "objections": [],
                            "decision_signals": []},
             "transcript": "The participant had a pain point with the interface workflow"},
        ]}
        vertical, conf, _ = classify_vertical(intel)
        assert vertical == "ux_research"

    def test_auto_classify_enriches(self):
        intel = {"segments": [
            {"extraction": {"topic": "pricing", "objections": ["too expensive"],
                            "decision_signals": ["send contract"]}},
        ]}
        enriched = auto_classify_and_extract(intel)
        assert "detected_vertical" in enriched
        assert "vertical_confidence" in enriched


# ---------------------------------------------------------------------------
# G3  Cross-Call Pattern Mining
# ---------------------------------------------------------------------------
from temporalos.intelligence.pattern_miner import PatternMiner


class TestPatternMiner:
    def _make_intel(self, topic, risk, objections=None, signals=None):
        return {"segments": [{"extraction": {
            "topic": topic, "risk_score": risk, "sentiment": "neutral",
            "objections": objections or [], "decision_signals": signals or [],
        }}]}

    def test_add_and_mine(self):
        pm = PatternMiner()
        pm.add_call("c1", self._make_intel("pricing", 0.8, ["too expensive"]), rep="rep1")
        pm.add_call("c2", self._make_intel("pricing", 0.7, ["no budget"]), rep="rep1")
        pm.add_call("c3", self._make_intel("demo", 0.2, [], ["looks great"]), rep="rep2")
        patterns = pm.mine_patterns()
        assert isinstance(patterns, list)

    def test_empty_mine(self):
        pm = PatternMiner()
        patterns = pm.mine_patterns()
        assert patterns == []

    def test_rep_patterns(self):
        pm = PatternMiner()
        for i in range(5):
            pm.add_call(f"c{i}", self._make_intel("pricing", 0.3 + i * 0.1), rep="rep_a")
        patterns = pm.mine_patterns()
        assert isinstance(patterns, list)


# ---------------------------------------------------------------------------
# G4  Live Call Copilot
# ---------------------------------------------------------------------------
from temporalos.intelligence.copilot import LiveCopilot, CopilotPrompt


class TestLiveCopilot:
    def test_competitor_battlecard(self):
        copilot = LiveCopilot()
        prompts = copilot.process_segment({
            "transcript": "We are currently using Gong for our team",
            "timestamp_ms": 5000,
            "extraction": {"risk_score": 0.3, "objections": [], "decision_signals": []},
        })
        assert any(p.type == "battlecard" for p in prompts)
        bc = [p for p in prompts if p.type == "battlecard"][0]
        assert bc.metadata["competitor"] == "gong"

    def test_risk_warning(self):
        copilot = LiveCopilot()
        prompts = copilot.process_segment({
            "transcript": "this is concerning",
            "timestamp_ms": 10000,
            "extraction": {"risk_score": 0.85, "objections": [], "decision_signals": []},
        })
        assert any(p.type == "risk_warning" for p in prompts)

    def test_objection_alert(self):
        copilot = LiveCopilot()
        prompts = copilot.process_segment({
            "transcript": "that's too expensive for us",
            "timestamp_ms": 15000,
            "extraction": {"risk_score": 0.5, "objections": ["too expensive"],
                           "decision_signals": []},
        })
        assert any(p.type == "objection_alert" for p in prompts)

    def test_closing_prompt(self):
        copilot = LiveCopilot()
        prompts = copilot.process_segment({
            "transcript": "I think we should move forward",
            "timestamp_ms": 20000,
            "extraction": {"risk_score": 0.1, "objections": [],
                           "decision_signals": ["move forward"]},
        })
        assert any(p.type == "closing_prompt" for p in prompts)

    def test_session_summary(self):
        copilot = LiveCopilot()
        copilot.process_segment({
            "transcript": "hello", "timestamp_ms": 0,
            "extraction": {"risk_score": 0.3, "objections": [], "decision_signals": []},
        })
        summary = copilot.get_session_summary()
        assert summary["segments_processed"] == 1
        assert "total_prompts" in summary

    def test_reset(self):
        copilot = LiveCopilot()
        copilot.process_segment({
            "transcript": "test", "timestamp_ms": 0,
            "extraction": {"risk_score": 0.9, "objections": [], "decision_signals": []},
        })
        copilot.reset()
        assert copilot.get_session_summary()["segments_processed"] == 0


# ---------------------------------------------------------------------------
# G5  Visual Intelligence
# ---------------------------------------------------------------------------
from temporalos.intelligence.visual_intel import (
    analyze_frame, analyze_video_frames, detect_pricing_page, detect_competitors,
)


class TestVisualIntel:
    def test_detect_pricing(self):
        result = detect_pricing_page("Our Pro plan is $49/mo and Enterprise is $199/mo")
        assert result is not None
        assert result["price_count"] >= 2
        assert "pro" in result["tiers"]

    def test_detect_competitors(self):
        result = detect_competitors("We saw that Salesforce and HubSpot both offer CRM")
        assert result is not None
        assert "salesforce" in result["competitors"]

    def test_analyze_frame(self):
        dets = analyze_frame("Pro plan $99/mo. Compare with Gong pricing.", frame_index=5)
        types = [d.type for d in dets]
        assert "pricing_page" in types
        assert "competitor" in types

    def test_analyze_video_frames(self):
        frames = [
            {"ocr_text": "$49/mo basic plan", "frame_index": 0, "timestamp_ms": 0},
            {"ocr_text": "CEO and CTO org chart VP Engineering", "frame_index": 1, "timestamp_ms": 5000},
            {"ocr_text": "random text nothing special", "frame_index": 2, "timestamp_ms": 10000},
        ]
        result = analyze_video_frames(frames)
        assert result["total_frames"] == 3
        assert result["total_detections"] >= 2

    def test_no_detections(self):
        dets = analyze_frame("just some normal text about weather")
        assert dets == []


# ---------------------------------------------------------------------------
# G6  Collaborative Annotations
# ---------------------------------------------------------------------------
from temporalos.intelligence.annotations import AnnotationStore


class TestAnnotations:
    def test_create_and_get(self):
        store = AnnotationStore()
        ann = store.create("job1", "user1", 0, 5, 10, "objection", comment="price concern")
        assert ann.label == "objection"
        assert store.get(ann.id) is ann

    def test_update(self):
        store = AnnotationStore()
        ann = store.create("job1", "user1", 0, 0, 5, "risk")
        store.update(ann.id, label="positive", comment="actually good")
        assert ann.label == "positive"
        assert ann.comment == "actually good"

    def test_delete(self):
        store = AnnotationStore()
        ann = store.create("job1", "user1", 0, 0, 5, "question")
        assert store.delete(ann.id) is True
        assert store.get(ann.id) is None

    def test_list_for_job(self):
        store = AnnotationStore()
        store.create("job1", "user1", 0, 0, 5, "risk")
        store.create("job1", "user1", 1, 0, 5, "objection")
        store.create("job2", "user1", 0, 0, 5, "positive")
        assert len(store.list_for_job("job1")) == 2

    def test_label_summary(self):
        store = AnnotationStore()
        store.create("job1", "u1", 0, 0, 5, "risk")
        store.create("job1", "u1", 1, 0, 5, "risk")
        store.create("job1", "u2", 2, 0, 5, "objection")
        summary = store.label_summary("job1")
        assert summary["risk"] == 2
        assert summary["objection"] == 1

    def test_export_training_data(self):
        store = AnnotationStore()
        store.create("job1", "u1", 0, 0, 5, "decision_signal", comment="strong signal")
        data = store.export_training_data("job1")
        assert len(data) == 1
        assert data[0]["label"] == "decision_signal"

    def test_invalid_label_raises(self):
        store = AnnotationStore()
        with pytest.raises(ValueError, match="Invalid label"):
            store.create("job1", "u1", 0, 0, 5, "invalid_label")

    def test_resolve(self):
        store = AnnotationStore()
        ann = store.create("job1", "u1", 0, 0, 5, "risk")
        store.resolve(ann.id)
        assert ann.resolved is True


# ---------------------------------------------------------------------------
# G7  Smart Clip Reels
# ---------------------------------------------------------------------------
from temporalos.intelligence.clip_reels import generate_clips, build_reel, Clip, ClipReel


class TestClipReels:
    def _segments(self):
        return [
            {"transcript": "Our pricing is $99/mo per seat", "timestamp_ms": 0,
             "duration_ms": 30000,
             "extraction": {"topic": "pricing", "risk_score": 0.3,
                            "objections": ["too expensive"],
                            "decision_signals": []}},
            {"transcript": "We currently use Gong for recording", "timestamp_ms": 30000,
             "duration_ms": 30000,
             "extraction": {"topic": "tools", "risk_score": 0.5,
                            "objections": [],
                            "decision_signals": []}},
            {"transcript": "I think we should send the contract", "timestamp_ms": 60000,
             "duration_ms": 30000,
             "extraction": {"topic": "closing", "risk_score": 0.1,
                            "objections": [],
                            "decision_signals": ["send contract"]}},
        ]

    def test_generate_clips(self):
        clips = generate_clips("job1", self._segments())
        assert len(clips) > 0
        assert all(isinstance(c, Clip) for c in clips)

    def test_build_reel(self):
        reel = build_reel("Test Reel", "job1", self._segments())
        assert isinstance(reel, ClipReel)
        assert reel.name == "Test Reel"
        assert len(reel.clips) > 0
        assert reel.total_duration_ms > 0

    def test_category_filter(self):
        clips = generate_clips("job1", self._segments(), categories=["competitor_mention"])
        for c in clips:
            assert c.category == "competitor_mention"

    def test_reel_to_dict(self):
        reel = build_reel("Dict Test", "job1", self._segments())
        d = reel.to_dict()
        assert "clips" in d
        assert d["name"] == "Dict Test"

    def test_empty_segments(self):
        clips = generate_clips("job1", [])
        assert clips == []


# ---------------------------------------------------------------------------
# G8  Active Learning
# ---------------------------------------------------------------------------
from temporalos.intelligence.active_learning import (
    ActiveLearningQueue, ReviewStatus, ReviewItem,
)


class TestActiveLearning:
    def test_gate_below_threshold(self):
        q = ActiveLearningQueue(confidence_threshold=0.6)
        item = q.gate("job1", 0, {"topic": "pricing"}, 0.4)
        assert item is not None
        assert item.status == ReviewStatus.PENDING

    def test_gate_above_threshold(self):
        q = ActiveLearningQueue(confidence_threshold=0.6)
        item = q.gate("job1", 0, {"topic": "pricing"}, 0.8)
        assert item is None

    def test_claim_and_approve(self):
        q = ActiveLearningQueue(0.6)
        item = q.gate("job1", 0, {"topic": "test"}, 0.3)
        claimed = q.claim(item.id, "reviewer1")
        assert claimed.status == ReviewStatus.IN_REVIEW
        approved = q.approve(item.id, "reviewer1", "looks good")
        assert approved.status == ReviewStatus.APPROVED

    def test_correct(self):
        q = ActiveLearningQueue(0.6)
        item = q.gate("job1", 0, {"topic": "wrong"}, 0.2)
        corrected = q.correct(item.id, "reviewer1", {"topic": "right"}, "fixed topic")
        assert corrected.status == ReviewStatus.CORRECTED
        assert corrected.corrected_extraction == {"topic": "right"}

    def test_reject(self):
        q = ActiveLearningQueue(0.6)
        item = q.gate("job1", 0, {"topic": "garbage"}, 0.1)
        rejected = q.reject(item.id, "reviewer1", "not valid")
        assert rejected.status == ReviewStatus.REJECTED

    def test_export_training_data(self):
        q = ActiveLearningQueue(0.6)
        item1 = q.gate("job1", 0, {"topic": "a"}, 0.3)
        item2 = q.gate("job1", 1, {"topic": "b"}, 0.2)
        q.approve(item1.id, "r1")
        q.correct(item2.id, "r1", {"topic": "b_fixed"})
        data = q.export_training_data()
        assert len(data) == 2
        sources = {d["source"] for d in data}
        assert "human_approved" in sources
        assert "human_corrected" in sources

    def test_metrics(self):
        q = ActiveLearningQueue(0.6)
        q.gate("job1", 0, {}, 0.3)
        q.gate("job1", 1, {}, 0.4)
        m = q.metrics()
        assert m["total_items"] == 2
        assert m["threshold"] == 0.6

    def test_queue_ordering(self):
        q = ActiveLearningQueue(0.6)
        q.gate("job1", 0, {}, 0.5)
        q.gate("job1", 1, {}, 0.1)
        q.gate("job1", 2, {}, 0.3)
        queue = q.get_queue(status=ReviewStatus.PENDING)
        confs = [i.confidence for i in queue]
        assert confs == sorted(confs)  # lowest first
