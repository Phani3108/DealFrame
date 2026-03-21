"""Phase B E2E test — Integrations.

Tests all 10 integrations:
  Zoom, Google Meet, Teams, Slack, Notion, Salesforce, HubSpot, Zapier,
  LangChain tool, LlamaIndex reader.

All outbound HTTP calls are mocked via patch on
temporalos.integrations.base.http_post / http_get.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


def _mock_http_post(url: str, payload, headers, timeout=15):
    return 201, {"id": "mock-id-123", "success": True, "url": "https://notion.so/p/mock"}


def _mock_http_get(url: str, params=None, headers=None, timeout=15):
    return 200, {"results": [], "id": "mock-get"}


# ── Zoom ──────────────────────────────────────────────────────────────────────

class TestZoomIntegration:
    def test_verify_signature_valid(self):
        from temporalos.integrations.zoom import verify_zoom_signature
        secret = "test_secret_123"
        ts = str(int(time.time()))
        body = '{"event":"recording.completed"}'
        msg = f"v0:{ts}:{body}"
        expected = "v0=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        assert verify_zoom_signature(secret, ts, body, expected) is True

    def test_verify_signature_invalid(self):
        from temporalos.integrations.zoom import verify_zoom_signature
        assert verify_zoom_signature("secret", "123", "body", "v0=wrong") is False

    def test_parse_recording_completed(self):
        from temporalos.integrations.zoom import parse_recording_completed
        payload = {
            "event": "recording.completed",
            "payload": {
                "object": {
                    "topic": "Sales Call — Acme Corp",
                    "id": "meeting_id_abc",
                    "host_email": "rep@example.com",
                    "start_time": "2024-01-15T10:00:00Z",
                    "duration": 45,
                    "recording_files": [
                        {"file_type": "MP4", "download_url": "https://zoom.us/rec/download/xyz"},
                        {"file_type": "TRANSCRIPT", "download_url": "https://zoom.us/rec/download/abc"},
                    ],
                }
            },
        }
        parsed = parse_recording_completed(payload)
        assert parsed["topic"] == "Sales Call — Acme Corp"
        assert parsed["meeting_id"] == "meeting_id_abc"
        assert "zoom.us" in parsed["download_url"]
        assert parsed["file_type"] == "MP4"
        assert parsed["duration_min"] == 45


# ── Google Meet ───────────────────────────────────────────────────────────────

class TestGoogleMeetIntegration:
    def test_build_auth_url(self):
        from temporalos.integrations.meet import build_auth_url
        url = build_auth_url("client_id_xyz", "https://myapp.com/callback", state="state123")
        assert "client_id_xyz" in url
        assert "state123" in url
        assert "accounts.google.com" in url

    def test_parse_calendar_notification(self):
        from temporalos.integrations.meet import parse_calendar_notification
        headers = {
            "X-Goog-Channel-Id": "chan-123",
            "X-Goog-Resource-Id": "res-456",
            "X-Goog-Resource-State": "exists",
        }
        result = parse_calendar_notification(headers)
        assert result["channel_id"] == "chan-123"
        assert result["resource_id"] == "res-456"
        assert result["resource_state"] == "exists"

    def test_find_recording_in_drive_mock(self):
        from temporalos.integrations.meet import find_recording_in_drive
        mock_drive = MagicMock()
        mock_drive.files().list().execute.return_value = {
            "files": [{"id": "file-123", "name": "Acme Sales Call.mp4", "mimeType": "video/mp4"}]
        }
        result = find_recording_in_drive(mock_drive, "Acme Sales Call", "rep@example.com")
        assert result is not None
        assert result["id"] == "file-123"


# ── Microsoft Teams ───────────────────────────────────────────────────────────

class TestTeamsIntegration:
    def test_handle_validation_token(self):
        from temporalos.integrations.teams import handle_validation_token
        payload = {"validationToken": "abc123-validation"}
        result = handle_validation_token(payload)
        assert result == "abc123-validation"

    def test_validate_notification_with_state(self):
        from temporalos.integrations.teams import validate_notification
        payload = {"value": [{"clientState": "my-secret"}]}
        assert validate_notification(payload, "my-secret") is True
        assert validate_notification(payload, "wrong-secret") is False

    def test_parse_call_record_notification(self):
        from temporalos.integrations.teams import parse_call_record_notification
        payload = {
            "value": [
                {"resourceData": {"@odata.type": "#microsoft.graph.callRecord", "id": "call-abc"},
                 "subscriptionId": "sub-123", "changeType": "created"},
            ]
        }
        records = parse_call_record_notification(payload)
        assert len(records) == 1
        assert records[0]["call_record_id"] == "call-abc"
        assert records[0]["change_type"] == "created"


# ── Slack ─────────────────────────────────────────────────────────────────────

class TestSlackIntegration:
    def test_verify_slack_signature_valid(self):
        from temporalos.integrations.slack import verify_slack_signature
        secret = "slack_signing_secret_xyz"
        ts = str(int(time.time()))
        body = "command=/temporalos&text=digest"
        base = f"v0:{ts}:{body}"
        expected = "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
        assert verify_slack_signature(secret, ts, body, expected) is True

    def test_parse_slash_command(self):
        from temporalos.integrations.slack import parse_slash_command
        form = {"command": "/temporalos", "text": "search pricing objections", "user_id": "U123", "channel_id": "C456"}
        cmd = parse_slash_command(form)
        assert cmd["command"] == "/temporalos"
        assert cmd["text"] == "search pricing objections"
        assert cmd["user_id"] == "U123"

    def test_build_risk_alert_blocks(self):
        from temporalos.integrations.slack import build_risk_alert_blocks
        blocks = build_risk_alert_blocks("job-abc", 0.85, ["pricing too high", "budget concerns"])
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    def test_post_message_mocked(self):
        from temporalos.integrations.slack import post_message
        with patch("temporalos.integrations.slack.http_post", return_value=(200, {"ok": True})):
            result = post_message("xoxb-token", "C123", "Hello from TemporalOS")
        assert result["ok"] is True


# ── Notion ────────────────────────────────────────────────────────────────────

class TestNotionIntegration:
    def _sample_intel(self):
        return {
            "duration_ms": 60_000,
            "overall_risk_score": 0.75,
            "segments": [
                {"extraction": {"topic": "pricing", "objections": ["too expensive"], "decision_signals": []}}
            ],
        }

    def test_build_page_properties(self):
        from temporalos.integrations.notion import build_page_properties
        props = build_page_properties("job-123", self._sample_intel())
        assert "Job ID" in props
        assert "Risk Score (%)" in props
        assert props["Risk Score (%)"]["number"] == 75

    def test_create_page_mocked(self):
        from temporalos.integrations.notion import create_page
        with patch("temporalos.integrations.notion.http_post",
                   return_value=(201, {"id": "page-xyz", "url": "https://notion.so/page-xyz"})):
            result = create_page("token", "db-id", "job-123", self._sample_intel())
        assert result["status"] == 201
        assert result["page_id"] == "page-xyz"


# ── Salesforce ────────────────────────────────────────────────────────────────

class TestSalesforceIntegration:
    def _sample_intel(self):
        return {
            "overall_risk_score": 0.65,
            "segments": [
                {"extraction": {"objections": ["pricing concerns"], "decision_signals": ["evaluate next quarter"]}}
            ],
        }

    def test_build_description(self):
        from temporalos.integrations.salesforce import build_description
        desc = build_description("job-123", self._sample_intel())
        assert "job-123" in desc
        assert "pricing concerns" in desc

    def test_sync_job_mocked(self):
        from temporalos.integrations.salesforce import sync_job
        with patch("temporalos.integrations.salesforce.http_post",
                   return_value=(201, {"id": "task-abc", "success": True})):
            result = sync_job("https://myorg.my.salesforce.com", "access_token", "job-123", self._sample_intel())
        assert result["http_status"] == 201
        assert result["task_id"] == "task-abc"


# ── HubSpot ───────────────────────────────────────────────────────────────────

class TestHubSpotIntegration:
    def _sample_intel(self):
        return {
            "overall_risk_score": 0.45,
            "segments": [
                {"extraction": {"objections": [], "decision_signals": ["schedule a demo"]}}
            ],
        }

    def test_build_note_body(self):
        from temporalos.integrations.hubspot import build_note_body
        body = build_note_body("job-456", self._sample_intel())
        assert "job-456" in body
        assert "schedule a demo" in body

    def test_sync_job_mocked(self):
        from temporalos.integrations.hubspot import sync_job
        with patch("temporalos.integrations.hubspot.http_post",
                   return_value=(201, {"id": "note-xyz"})):
            result = sync_job("hs-token", "job-456", self._sample_intel(), ["contact-1"])
        assert result["http_status"] == 201
        assert result["note_id"] == "note-xyz"


# ── Zapier ────────────────────────────────────────────────────────────────────

class TestZapierIntegration:
    def test_subscribe_and_list(self):
        from temporalos.integrations.zapier import ZapierSubscriptionManager
        mgr = ZapierSubscriptionManager()
        sub = mgr.subscribe("https://hooks.zapier.com/abc", "job.completed")
        assert sub["target_url"] == "https://hooks.zapier.com/abc"
        assert len(mgr.list_all()) == 1

    def test_unsubscribe(self):
        from temporalos.integrations.zapier import ZapierSubscriptionManager
        mgr = ZapierSubscriptionManager()
        mgr.subscribe("https://hooks.zapier.com/xyz", "risk.high_detected")
        ok = mgr.unsubscribe("https://hooks.zapier.com/xyz")
        assert ok is True
        assert len(mgr.list_all()) == 0

    def test_build_event_payload(self):
        from temporalos.integrations.zapier import build_event_payload
        intel = {"overall_risk_score": 0.8, "segments": [
            {"extraction": {"objections": ["pricing"], "decision_signals": ["move forward"], "topic": "deal"}}
        ]}
        payload = build_event_payload("job.completed", "job-789", intel)
        assert payload["event"] == "job.completed"
        assert payload["risk_score_pct"] == 80
        assert "pricing" in payload["top_objections"]

    def test_deliver_hook_mocked(self):
        from temporalos.integrations.zapier import deliver_hook
        with patch("temporalos.integrations.zapier.http_post",
                   return_value=(200, {"status": "success"})):
            result = deliver_hook("https://hooks.zapier.com/x", "job.completed",
                                  "job-000", {}, secret="secret")
        assert result["http_status"] == 200


# ── LangChain Tool ────────────────────────────────────────────────────────────

class TestLangChainTool:
    def test_tool_instantiates(self):
        from temporalos.integrations.langchain_tool import TemporalOSTool
        tool = TemporalOSTool(base_url="http://localhost:8000")
        assert tool.name == "temporalos_search"
        assert "video" in tool.description.lower() or "temporalos" in tool.description.lower()

    def test_tool_run_mocked(self):
        from temporalos.integrations.langchain_tool import TemporalOSTool
        tool = TemporalOSTool()
        with patch("temporalos.integrations.langchain_tool.TemporalOSTool.ask",
                   return_value="Found 2 segments with pricing objections."):
            result = tool.run("What are the pricing objections?")
        assert "pricing" in result.lower() or "segment" in result.lower()


# ── LlamaIndex Reader ─────────────────────────────────────────────────────────

class TestLlamaIndexReader:
    def test_reader_instantiates(self):
        from temporalos.integrations.llamaindex_reader import TemporalOSReader
        reader = TemporalOSReader(base_url="http://localhost:8000")
        assert reader.base_url == "http://localhost:8000"

    def test_job_to_docs(self):
        from temporalos.integrations.llamaindex_reader import TemporalOSReader
        reader = TemporalOSReader()
        job_data = {
            "segments": [
                {"timestamp_str": "00:00", "transcript": "We need a discount.",
                 "extraction": {"topic": "pricing", "risk": "high", "risk_score": 0.8,
                                "objections": ["too expensive"], "decision_signals": []}},
            ]
        }
        docs = reader._job_to_docs("job-abc", job_data)
        assert len(docs) == 1
        assert "pricing" in docs[0].text
        assert docs[0].metadata["job_id"] == "job-abc"

    def test_load_data_mocked(self):
        from temporalos.integrations.llamaindex_reader import TemporalOSReader
        reader = TemporalOSReader()
        with patch("temporalos.integrations.llamaindex_reader.TemporalOSReader._load_job",
                   return_value=[]):
            docs = reader.load_data(job_ids=["job-xyz"])
        assert isinstance(docs, list)
