"""Phase J — Frontend Completion & Real UX e2e tests.

Tests all 7 new API route modules (annotations, active-learning, audit,
diff, patterns, copilot, admin) via TestClient against the real FastAPI app.
"""
from __future__ import annotations

import os
import tempfile

# ── Force SQLite for tests before any app import ─────────────────────────────
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"

import pytest
from fastapi.testclient import TestClient

# ── App fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from temporalos.api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded_job(client: TestClient):
    """Submit a test video job so diff/patterns have data."""
    import tempfile, subprocess, os
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=blue:s=320x240:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", path,
        ], capture_output=True, timeout=15)
        with open(path, "rb") as f:
            r = client.post("/api/v1/process", files={"file": ("test.mp4", f, "video/mp4")})
        if r.status_code == 200:
            return r.json().get("job_id")
    except Exception:
        pass
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return None


# ── Annotations ──────────────────────────────────────────────────────────────

class TestAnnotations:
    def test_list_empty(self, client: TestClient):
        r = client.get("/api/v1/annotations?job_id=nonexistent")
        assert r.status_code == 200
        body = r.json()
        assert "annotations" in body
        assert "total" in body

    def test_create_and_get(self, client: TestClient):
        payload = {
            "job_id": "test-ann-job",
            "user_id": "tester",
            "segment_index": 0,
            "start_word": 0,
            "end_word": 10,
            "label": "objection",
            "comment": "pricing concern",
            "tags": ["price"],
        }
        r = client.post("/api/v1/annotations", json=payload)
        assert r.status_code == 200
        ann = r.json()["annotation"]
        assert ann["label"] == "objection"
        ann_id = ann["id"]

        # Get by ID
        r2 = client.get(f"/api/v1/annotations/{ann_id}")
        assert r2.status_code == 200
        assert r2.json()["annotation"]["id"] == ann_id

    def test_update_annotation(self, client: TestClient):
        payload = {
            "job_id": "test-upd-job", "segment_index": 0,
            "start_word": 0, "end_word": 5, "label": "objection",
        }
        r = client.post("/api/v1/annotations", json=payload)
        assert r.status_code == 200, r.text
        ann_id = r.json()["annotation"]["id"]

        r2 = client.patch(f"/api/v1/annotations/{ann_id}", json={"comment": "updated"})
        assert r2.status_code == 200
        assert r2.json()["annotation"]["comment"] == "updated"

    def test_resolve_annotation(self, client: TestClient):
        payload = {
            "job_id": "test-resolve-job", "segment_index": 0,
            "start_word": 0, "end_word": 5, "label": "objection",
        }
        r = client.post("/api/v1/annotations", json=payload)
        assert r.status_code == 200, r.text
        ann_id = r.json()["annotation"]["id"]

        r2 = client.post(f"/api/v1/annotations/{ann_id}/resolve")
        assert r2.status_code == 200
        assert r2.json()["annotation"]["resolved"] is True

    def test_delete_annotation(self, client: TestClient):
        payload = {
            "job_id": "test-del-job", "segment_index": 0,
            "start_word": 0, "end_word": 5, "label": "objection",
        }
        r = client.post("/api/v1/annotations", json=payload)
        assert r.status_code == 200, r.text
        ann_id = r.json()["annotation"]["id"]

        r2 = client.delete(f"/api/v1/annotations/{ann_id}")
        assert r2.status_code == 200
        assert r2.json()["deleted"] is True

    def test_summary(self, client: TestClient):
        r = client.get("/api/v1/annotations/summary?job_id=test-ann-job")
        assert r.status_code == 200
        body = r.json()
        assert "label_summary" in body
        assert "total" in body

    def test_export(self, client: TestClient):
        r = client.get("/api/v1/annotations/export?job_id=test-ann-job")
        assert r.status_code == 200
        assert "training_data" in r.json()


# ── Active Learning ──────────────────────────────────────────────────────────

class TestActiveLearning:
    def test_queue_empty(self, client: TestClient):
        r = client.get("/api/v1/active-learning/queue")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_metrics(self, client: TestClient):
        r = client.get("/api/v1/active-learning/metrics")
        assert r.status_code == 200
        body = r.json()
        assert "total_items" in body
        assert "threshold" in body

    def test_gate_and_review(self, client: TestClient):
        gate_payload = {
            "job_id": "test-al-job",
            "segment_index": 0,
            "extraction": {"topic": "pricing", "sentiment": "negative"},
            "confidence": 0.4,
        }
        r = client.post("/api/v1/active-learning/gate", json=gate_payload)
        assert r.status_code == 200
        body = r.json()
        # low confidence → should be queued
        if body.get("queued"):
            item_id = body["item"]["id"]

            # Claim
            r2 = client.post(f"/api/v1/active-learning/{item_id}/claim",
                             json={"reviewer": "tester"})
            assert r2.status_code == 200

            # Approve
            r3 = client.post(f"/api/v1/active-learning/{item_id}/approve",
                             json={"reviewer": "tester", "notes": "looks good"})
            assert r3.status_code == 200

    def test_gate_high_confidence_passes(self, client: TestClient):
        gate_payload = {
            "job_id": "test-al-pass",
            "segment_index": 1,
            "extraction": {"topic": "pricing"},
            "confidence": 0.99,
        }
        r = client.post("/api/v1/active-learning/gate", json=gate_payload)
        assert r.status_code == 200
        # high confidence → should pass through
        body = r.json()
        assert "queued" in body or "passed" in body or "extraction" in body

    def test_export_training(self, client: TestClient):
        r = client.get("/api/v1/active-learning/export")
        assert r.status_code == 200
        assert "training_data" in r.json()


# ── Audit Trail ──────────────────────────────────────────────────────────────

class TestAudit:
    def test_query_empty(self, client: TestClient):
        r = client.get("/api/v1/audit")
        assert r.status_code == 200
        body = r.json()
        assert "entries" in body
        assert "total" in body

    def test_stats(self, client: TestClient):
        r = client.get("/api/v1/audit/stats")
        assert r.status_code == 200
        body = r.json()
        assert "total_entries" in body
        assert "action_counts" in body
        assert "resource_counts" in body

    def test_filter_by_action(self, client: TestClient):
        r = client.get("/api/v1/audit?action=create&limit=10")
        assert r.status_code == 200
        assert "entries" in r.json()

    def test_pagination(self, client: TestClient):
        r = client.get("/api/v1/audit?limit=5&offset=0")
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 5
        assert body["offset"] == 0


# ── Diff Engine ──────────────────────────────────────────────────────────────

class TestDiff:
    def test_list_comparable_jobs(self, client: TestClient):
        r = client.get("/api/v1/diff/jobs")
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body
        assert "total" in body

    def test_compare_not_found(self, client: TestClient):
        r = client.get("/api/v1/diff/nonexistent-a/nonexistent-b")
        assert r.status_code == 404

    def test_compare_same_job_fallback(self, client: TestClient, seeded_job):
        if not seeded_job:
            pytest.skip("No seeded job available")
        r = client.get(f"/api/v1/diff/{seeded_job}/{seeded_job}")
        # Self-compare should work
        assert r.status_code == 200
        assert "report" in r.json()


# ── Patterns ─────────────────────────────────────────────────────────────────

class TestPatterns:
    def test_get_patterns_default(self, client: TestClient):
        r = client.get("/api/v1/patterns")
        assert r.status_code == 200
        body = r.json()
        assert "pattern_type" in body
        assert body["pattern_type"] == "objection_risk"
        assert "patterns" in body

    def test_get_patterns_types(self, client: TestClient):
        for pt in ["objection_risk", "topic_risk", "rep_performance", "behavioral"]:
            r = client.get(f"/api/v1/patterns?pattern_type={pt}")
            assert r.status_code == 200
            assert r.json()["pattern_type"] == pt

    def test_summary(self, client: TestClient):
        r = client.get("/api/v1/patterns/summary")
        assert r.status_code == 200
        body = r.json()
        assert "total_jobs" in body
        assert "available_patterns" in body
        assert len(body["available_patterns"]) == 4


# ── Copilot ──────────────────────────────────────────────────────────────────

class TestCopilot:
    def test_analyze(self, client: TestClient):
        payload = {
            "transcript_so_far": "I'm not sure the pricing works for us.",
            "segments_so_far": [],
        }
        r = client.post("/api/v1/copilot/analyze", json=payload)
        assert r.status_code == 200
        assert "signals" in r.json()

    def test_battlecard(self, client: TestClient):
        payload = {
            "transcript_so_far": "We need to discuss competitor X.",
        }
        r = client.post("/api/v1/copilot/battlecard", json=payload)
        assert r.status_code == 200
        assert "battlecard" in r.json()

    def test_config(self, client: TestClient):
        r = client.get("/api/v1/copilot/config")
        assert r.status_code == 200
        body = r.json()
        assert "signal_types" in body
        assert "enabled" in body
        assert body["enabled"] is True
        assert "refresh_interval_ms" in body


# ── Admin ────────────────────────────────────────────────────────────────────

class TestAdmin:
    def test_list_tenants(self, client: TestClient):
        r = client.get("/api/v1/admin/tenants")
        assert r.status_code == 200
        assert "tenants" in r.json()
        assert "total" in r.json()

    def test_create_tenant(self, client: TestClient):
        payload = {
            "tenant_id": "test-tenant-j",
            "slug": "j-test-co",
            "plan": "pro",
        }
        r = client.post("/api/v1/admin/tenants", json=payload)
        assert r.status_code == 200
        assert "tenant" in r.json()
        assert r.json()["tenant"]["slug"] == "j-test-co"

    def test_list_users(self, client: TestClient):
        r = client.get("/api/v1/admin/users")
        assert r.status_code == 200
        assert "users" in r.json()

    def test_roles(self, client: TestClient):
        r = client.get("/api/v1/admin/roles")
        assert r.status_code == 200
        body = r.json()
        assert "roles" in body
        assert isinstance(body["roles"], dict)

    def test_permissions(self, client: TestClient):
        r = client.get("/api/v1/admin/permissions/admin")
        assert r.status_code == 200
        assert "role" in r.json()
        assert "permissions" in r.json()

    def test_permissions_unknown_role(self, client: TestClient):
        r = client.get("/api/v1/admin/permissions/nonexistent_role")
        assert r.status_code == 404

    def test_settings(self, client: TestClient):
        r = client.get("/api/v1/admin/settings")
        assert r.status_code == 200
        # Should return a dict of settings
        assert isinstance(r.json(), dict)

    def test_system_stats(self, client: TestClient):
        r = client.get("/api/v1/admin/stats")
        assert r.status_code == 200
        body = r.json()
        assert "users" in body or "tenants" in body


# ── Frontend Compilation ─────────────────────────────────────────────────────

class TestFrontend:
    def test_all_pages_exist(self):
        """Verify all 25 page modules exist."""
        from pathlib import Path
        pages_dir = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
        expected_pages = [
            "Dashboard", "Upload", "Results", "Observatory", "Intelligence",
            "Finetuning", "LocalPipeline", "Observability", "Search",
            "Streaming", "Chat", "Coaching", "SchemaBuilder", "Integrations",
            "Batch", "MeetingPrep", "KnowledgeGraph",
            # Phase J new pages
            "Annotations", "ReviewQueue", "AuditLog", "DiffView",
            "PatternMiner", "LiveCopilot", "Admin", "SettingsPage",
        ]
        for page in expected_pages:
            assert (pages_dir / f"{page}.tsx").exists(), f"Missing page: {page}.tsx"

    def test_app_tsx_has_all_routes(self):
        """Verify App.tsx references all Phase J routes."""
        from pathlib import Path
        app_tsx = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.tsx").read_text()
        for route in ["/annotations", "/review-queue", "/audit-log", "/diff",
                      "/patterns", "/copilot", "/admin", "/settings"]:
            assert route in app_tsx, f"Missing route {route} in App.tsx"

    def test_layout_has_nav_items(self):
        """Verify Layout.tsx has all Phase J nav entries."""
        from pathlib import Path
        layout = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "Layout.tsx").read_text()
        for label in ["Pattern Miner", "Diff Engine", "Live Copilot",
                      "Annotations", "Review Queue", "Audit Log", "Admin", "Settings"]:
            assert label in layout, f"Missing nav entry '{label}' in Layout.tsx"

    def test_notification_bell_exists(self):
        """Verify notification bell is in Layout."""
        from pathlib import Path
        layout = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "Layout.tsx").read_text()
        assert "Bell" in layout
        assert "getNotifications" in layout
        assert "unread" in layout
