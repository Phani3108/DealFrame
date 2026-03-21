"""Phase F E2E test — Real-World Workflows.

Tests: demo seed, auth, export, notifications, Zoom/Slack OAuth.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest


def _make_intel() -> Dict[str, Any]:
    return {
        "overall_risk_score": 0.5,
        "duration_ms": 60_000,
        "segments": [
            {
                "timestamp_str": "00:00", "timestamp_ms": 0,
                "transcript": "Discussion about pricing.",
                "extraction": {
                    "topic": "pricing", "sentiment": "neutral", "risk": "medium",
                    "risk_score": 0.5, "objections": ["too expensive"],
                    "decision_signals": ["send proposal"], "confidence": 0.8,
                },
            },
        ],
    }


# ── 1. Demo Seed Generator ────────────────────────────────────────────────────

class TestDemoSeed:
    def test_generate_seed_data(self):
        from scripts.seed_demo import generate_seed_data
        data = generate_seed_data(seed=42)
        assert data["total_calls"] >= 15
        assert len(data["companies"]) == 5
        assert len(data["reps"]) == 8
        for job_id, job in data["jobs"].items():
            assert "intelligence" in job
            assert len(job["intelligence"]["segments"]) >= 3

    def test_seed_is_deterministic(self):
        from scripts.seed_demo import generate_seed_data
        d1 = generate_seed_data(seed=42)
        d2 = generate_seed_data(seed=42)
        assert list(d1["jobs"].keys()) == list(d2["jobs"].keys())


# ── 2. Authentication ─────────────────────────────────────────────────────────

class TestAuth:
    def test_register_and_login(self):
        from temporalos.auth import register, login
        result = register("test@example.com", "password123", display_name="Test User")
        assert result["email"] == "test@example.com"
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["api_key"].startswith("tos_")

        login_result = login("test@example.com", "password123")
        assert login_result["email"] == "test@example.com"
        assert "access_token" in login_result

    def test_login_wrong_password(self):
        from temporalos.auth import register, login
        try:
            register("wrong@example.com", "password123")
        except ValueError:
            pass  # may already exist
        with pytest.raises(ValueError, match="Invalid"):
            login("wrong@example.com", "wrongpassword")

    def test_duplicate_register(self):
        from temporalos.auth import register
        try:
            register("dup@example.com", "password123")
        except ValueError:
            pass
        with pytest.raises(ValueError, match="already registered"):
            register("dup@example.com", "password123")

    def test_refresh_token(self):
        from temporalos.auth import register, refresh_token
        result = register("refresh@example.com", "password123")
        new_tokens = refresh_token(result["refresh_token"])
        assert "access_token" in new_tokens

    def test_password_too_short(self):
        from temporalos.auth import register
        with pytest.raises(ValueError, match="at least 8"):
            register("short@example.com", "123")

    def test_rate_limiting(self):
        from temporalos.auth import check_rate_limit
        email = "ratelimit@test.com"
        for _ in range(10):
            assert check_rate_limit(email, "free") is True
        assert check_rate_limit(email, "free") is False

    def test_token_decode(self):
        from temporalos.auth import _create_token, _decode_token
        from datetime import timedelta
        token = _create_token({"sub": "test@test.com", "role": "admin"}, timedelta(hours=1))
        payload = _decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test@test.com"


# ── 3. Export Engine ───────────────────────────────────────────────────────────

class TestExportEngine:
    def test_export_json(self):
        from temporalos.export import export
        intel = _make_intel()
        result = export("job1", intel, "json")
        parsed = json.loads(result)
        assert parsed["job_id"] == "job1"

    def test_export_csv(self):
        from temporalos.export import export
        intel = _make_intel()
        result = export("job1", intel, "csv")
        assert "job_id" in result
        assert "pricing" in result

    def test_export_markdown(self):
        from temporalos.export import export
        intel = _make_intel()
        result = export("job1", intel, "markdown")
        assert "# TemporalOS Report" in result
        assert "pricing" in result

    def test_export_html(self):
        from temporalos.export import export
        intel = _make_intel()
        result = export("job1", intel, "html")
        assert "<html>" in result
        assert "TemporalOS" in result

    def test_unsupported_format(self):
        from temporalos.export import export
        with pytest.raises(ValueError, match="Unsupported"):
            export("job1", {}, "pdf_fake")


# ── 4. Notifications ──────────────────────────────────────────────────────────

class TestNotifications:
    def test_send_and_get(self):
        from temporalos.notifications import NotificationService
        svc = NotificationService()
        svc.send("user1", "risk_alert", "High Risk", "Risk detected.")
        svc.send("user1", "batch_complete", "Batch Done", "5 processed.")

        all_notifs = svc.get_all("user1")
        assert len(all_notifs) == 2
        assert svc.unread_count("user1") == 2

    def test_mark_read(self):
        from temporalos.notifications import NotificationService
        svc = NotificationService()
        n = svc.send("user2", "drift", "Drift", "Model drift detected.")
        svc.mark_read("user2", n.id)
        assert svc.unread_count("user2") == 0

    def test_mark_all_read(self):
        from temporalos.notifications import NotificationService
        svc = NotificationService()
        svc.send("user3", "risk_alert", "Alert 1", "msg1")
        svc.send("user3", "risk_alert", "Alert 2", "msg2")
        count = svc.mark_all_read("user3")
        assert count == 2
        assert svc.unread_count("user3") == 0

    def test_event_shortcuts(self):
        from temporalos.notifications import NotificationService
        svc = NotificationService()
        n = svc.notify_risk_alert("u1", "Acme", 0.85, "threshold", "job1")
        assert "Acme" in n.title
        n2 = svc.notify_batch_complete("u1", "batch-1", 5, 1)
        assert "batch-1" in n2.title


# ── 5. Zoom OAuth ─────────────────────────────────────────────────────────────

class TestZoomOAuth:
    def test_authorize_url(self):
        from temporalos.integrations.zoom_oauth import ZoomOAuth
        z = ZoomOAuth(client_id="test_id", client_secret="test_secret")
        url = z.get_authorize_url(state="abc123")
        assert "zoom.us/oauth/authorize" in url
        assert "test_id" in url
        assert "abc123" in url

    def test_webhook_verify(self):
        from temporalos.integrations.zoom_oauth import ZoomOAuth
        import hashlib, hmac
        secret = "test_webhook_secret"
        z = ZoomOAuth(webhook_secret=secret)
        payload = b'{"event":"recording.completed"}'
        timestamp = "1234567890"
        message = f"v0:{timestamp}:{payload.decode()}"
        sig = "v0=" + hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        assert z.verify_webhook(payload, sig, timestamp) is True
        assert z.verify_webhook(payload, "v0=invalid", timestamp) is False

    def test_token_store(self):
        from temporalos.integrations.zoom_oauth import ZoomOAuth
        z = ZoomOAuth()
        z.store_tokens("user1", {"access_token": "abc"})
        assert z.get_tokens("user1")["access_token"] == "abc"
        assert z.get_tokens("user2") is None


# ── 6. Slack OAuth ─────────────────────────────────────────────────────────────

class TestSlackOAuth:
    def test_install_url(self):
        from temporalos.integrations.slack_oauth import SlackOAuth
        s = SlackOAuth(client_id="slack_test_id")
        url = s.get_install_url(state="state123")
        assert "slack.com/oauth" in url
        assert "slack_test_id" in url

    def test_slash_command_help(self):
        from temporalos.integrations.slack_oauth import handle_slash_command
        result = handle_slash_command("/tos", "help", "user1")
        assert "Commands" in result["text"]

    def test_slash_command_status(self):
        from temporalos.integrations.slack_oauth import handle_slash_command
        result = handle_slash_command("/tos", "status", "user1")
        assert "running" in result["text"]

    def test_request_verify(self):
        from temporalos.integrations.slack_oauth import SlackOAuth
        import hashlib, hmac, time
        secret = "slack_sign_secret"
        s = SlackOAuth(signing_secret=secret)
        body = b"token=test&command=/tos"
        ts = str(int(time.time()))
        sig_basestring = f"v0:{ts}:{body.decode()}"
        sig = "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
        assert s.verify_request(body, sig, ts) is True
