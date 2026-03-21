"""TemporalOS Python SDK — TemporalOSClient."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from temporalos.sdk.types import (
    BatchJob, CoachingCard, Intelligence, Job, MeetingBrief,
    QAAnswer, RiskAlert, Schema, SearchResult, Webhook,
)


class TemporalOSError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


class TemporalOSClient:
    """Synchronous Python client for the TemporalOS API.

    All methods raise TemporalOSError on non-2xx responses.

    Quick start:
        client = TemporalOSClient(base_url="http://localhost:8000")
        job_id = client.submit_url("https://example.com/call.mp4")
        job_id = client.wait_until_ready(job_id)
        intel = client.get_intelligence(job_id)
        answer = client.ask("What were the top objections?")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def _request(self, method: str, path: str,
                  payload: Optional[Dict] = None,
                  params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode()
            try:
                detail = json.loads(err_body).get("detail", err_body[:200])
            except Exception:
                detail = err_body[:200]
            raise TemporalOSError(exc.code, detail) from exc

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        return self._request("POST", path, payload=payload)

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Core — job submission & retrieval
    # ------------------------------------------------------------------

    def submit_url(self, url: str, vertical: str = "",
                   schema_id: str = "") -> str:
        """Submit a video URL for processing. Returns job_id."""
        resp = self._post("/api/v1/process/url", {
            "url": url, "vertical": vertical, "schema_id": schema_id,
        })
        return resp["job_id"]

    def get_job(self, job_id: str) -> Job:
        resp = self._get(f"/api/v1/process/{job_id}")
        return Job.from_dict(resp)

    def wait_until_ready(self, job_id: str, poll_interval: float = 2.0,
                         max_wait: float = 300.0) -> str:
        """Poll until the job is completed or failed. Returns job_id."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job.status in ("completed", "failed", "partial"):
                return job_id
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {max_wait}s")

    def get_intelligence(self, job_id: str) -> Intelligence:
        resp = self._get(f"/api/v1/intelligence/{job_id}")
        return Intelligence.from_dict(resp)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20,
               risk_min: Optional[float] = None,
               topic: Optional[str] = None) -> List[SearchResult]:
        params: Dict[str, str] = {"q": query, "limit": str(limit)}
        if risk_min is not None:
            params["risk_min"] = str(risk_min)
        if topic:
            params["topic"] = topic
        resp = self._get("/api/v1/search", params)
        return [SearchResult.from_dict(r) for r in resp.get("results", [])]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def get_summary(self, job_id: str,
                    summary_type: str = "executive",
                    custom_template: str = "") -> Dict[str, Any]:
        resp = self._post(f"/api/v1/summaries/{job_id}", {
            "summary_type": summary_type,
            "custom_template": custom_template,
        })
        return resp.get("summary", resp)

    # ------------------------------------------------------------------
    # Speaker Intelligence
    # ------------------------------------------------------------------

    def get_speakers(self, job_id: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/diarization/{job_id}/speakers")

    # ------------------------------------------------------------------
    # Clips
    # ------------------------------------------------------------------

    def list_clips(self, job_id: str) -> List[Dict[str, Any]]:
        return self._get(f"/api/v1/clips/{job_id}").get("clips", [])

    def extract_clip(self, job_id: str, label: str,
                     start_ms: int, end_ms: int) -> Dict[str, Any]:
        resp = self._post(f"/api/v1/clips/{job_id}/extract", {
            "label": label, "start_ms": start_ms, "end_ms": end_ms,
        })
        return resp.get("clip", resp)

    def extract_significant_clips(self, job_id: str, n: int = 5) -> List[Dict[str, Any]]:
        return self._post(f"/api/v1/clips/{job_id}/significant?n={n}",
                          {}).get("clips", [])

    # ------------------------------------------------------------------
    # Agents — Q&A
    # ------------------------------------------------------------------

    def ask(self, question: str, job_id: Optional[str] = None) -> QAAnswer:
        params: Dict[str, str] = {"q": question}
        if job_id:
            params["job_id"] = job_id
        resp = self._get("/api/v1/agents/qa", params)
        return QAAnswer.from_dict(resp)

    def index_for_qa(self, job_id: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/agents/qa/index/{job_id}")

    # ------------------------------------------------------------------
    # Agents — Risk
    # ------------------------------------------------------------------

    def get_risk_alerts(self) -> List[RiskAlert]:
        resp = self._get("/api/v1/agents/risk/alerts")
        return [RiskAlert.from_dict(a) for a in resp.get("alerts", [])]

    def record_risk(self, job_id: str, company: str = "",
                    deal_id: str = "") -> List[RiskAlert]:
        resp = self._post(f"/api/v1/agents/risk/record/{job_id}",
                          {"company": company, "deal_id": deal_id})
        return [RiskAlert.from_dict(a) for a in resp.get("alerts", [])]

    # ------------------------------------------------------------------
    # Agents — Coaching
    # ------------------------------------------------------------------

    def get_coaching_card(self, rep_id: str) -> CoachingCard:
        resp = self._get(f"/api/v1/agents/coaching/{rep_id}")
        return CoachingCard.from_dict(resp)

    def record_call_for_coaching(self, job_id: str, rep_id: str,
                                  speaker_label: str = "SPEAKER_A") -> Dict[str, Any]:
        return self._post(f"/api/v1/agents/coaching/record/{job_id}",
                          {"rep_id": rep_id, "speaker_label": speaker_label})

    # ------------------------------------------------------------------
    # Agents — Meeting Prep
    # ------------------------------------------------------------------

    def get_meeting_brief(self, company: str, contact: str = "") -> MeetingBrief:
        resp = self._post("/api/v1/agents/meeting-prep",
                          {"company": company, "contact": contact})
        return MeetingBrief.from_dict(resp)

    # ------------------------------------------------------------------
    # Agents — Knowledge Graph
    # ------------------------------------------------------------------

    def query_kg(self, entity: str) -> Dict[str, Any]:
        return self._get("/api/v1/agents/kg", {"entity": entity})

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def submit_batch(self, urls: List[str], vertical: str = "",
                     schema_id: str = "", webhook_url: str = "") -> BatchJob:
        resp = self._post("/api/v1/batch", {
            "urls": urls, "vertical": vertical,
            "schema_id": schema_id, "webhook_url": webhook_url,
        })
        return BatchJob.from_dict(resp)

    def get_batch(self, batch_id: str) -> BatchJob:
        return BatchJob.from_dict(self._get(f"/api/v1/batch/{batch_id}"))

    def wait_for_batch(self, batch_id: str, poll_interval: float = 3.0,
                       max_wait: float = 600.0) -> BatchJob:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            job = self.get_batch(batch_id)
            if job.status in ("completed", "failed", "partial"):
                return job
            time.sleep(poll_interval)
        raise TimeoutError(f"Batch {batch_id} did not complete within {max_wait}s")

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def list_webhooks(self) -> List[Webhook]:
        return [Webhook.from_dict(w) for w in
                self._get("/api/v1/webhooks").get("webhooks", [])]

    def create_webhook(self, url: str, events: List[str],
                       secret: str = "") -> Webhook:
        resp = self._post("/api/v1/webhooks",
                          {"url": url, "events": events, "secret": secret})
        return Webhook.from_dict(resp.get("webhook", resp))

    def delete_webhook(self, webhook_id: str) -> bool:
        resp = self._delete(f"/api/v1/webhooks/{webhook_id}")
        return resp.get("deleted", False)

    # ------------------------------------------------------------------
    # Custom schemas
    # ------------------------------------------------------------------

    def list_schemas(self) -> List[Schema]:
        return [Schema.from_dict(s) for s in
                self._get("/api/v1/schemas").get("schemas", [])]

    def create_schema(self, name: str, fields: List[Dict[str, Any]],
                      vertical: str = "") -> Schema:
        resp = self._post("/api/v1/schemas",
                          {"name": name, "fields": fields, "vertical": vertical})
        return Schema.from_dict(resp.get("schema", resp))

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        return self._get("/health")
