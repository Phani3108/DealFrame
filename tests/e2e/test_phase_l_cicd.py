"""Phase L — CI/CD, Security & Production Hardening e2e tests.

Tests:
- Security headers on all responses
- Health check probes (liveness, readiness)
- Docker Compose & CI workflow file existence
- CORS / CSP policy correctness
"""
from __future__ import annotations

import os
import tempfile

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_test_db_path}")

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


@pytest.fixture(scope="module")
def client():
    from temporalos.api.main import app
    with TestClient(app) as c:
        yield c


ROOT = Path(__file__).resolve().parents[2]


# ── Security Headers ────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_x_content_type_options(self, client: TestClient):
        r = client.get("/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client: TestClient):
        r = client.get("/health")
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, client: TestClient):
        r = client.get("/health")
        assert "1" in r.headers.get("X-XSS-Protection", "")

    def test_referrer_policy(self, client: TestClient):
        r = client.get("/health")
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client: TestClient):
        r = client.get("/health")
        pp = r.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_hsts(self, client: TestClient):
        r = client.get("/health")
        hsts = r.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts

    def test_csp(self, client: TestClient):
        r = client.get("/health")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_attribution_headers_preserved(self, client: TestClient):
        r = client.get("/health")
        assert r.headers.get("X-Powered-By") == "TemporalOS"
        assert "Phani" in r.headers.get("X-Author", "")
        assert r.headers.get("X-Copyright") is not None


# ── Health Check Probes ──────────────────────────────────────────────────────

class TestHealthProbes:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.1.0"

    def test_liveness(self, client: TestClient):
        r = client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_readiness(self, client: TestClient):
        r = client.get("/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ready", "degraded")
        assert "database" in body
        assert "jobs_in_memory" in body


# ── CI/CD Files ──────────────────────────────────────────────────────────────

class TestCICDFiles:
    def test_github_actions_workflow(self):
        ci_path = ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), "CI workflow file missing"
        content = ci_path.read_text()
        assert "pytest" in content
        assert "tsc" in content or "npm" in content
        assert "bandit" in content

    def test_docker_compose(self):
        dc = ROOT / "docker-compose.yml"
        assert dc.exists()
        content = dc.read_text()
        assert "postgres" in content
        assert "healthcheck" in content
        assert "frontend" in content

    def test_dockerfile_exists(self):
        df = ROOT / "Dockerfile"
        assert df.exists(), "Dockerfile missing"

    def test_makefile_exists(self):
        mk = ROOT / "Makefile"
        assert mk.exists(), "Makefile missing"


# ── API Error Handling ───────────────────────────────────────────────────────

class TestErrorHandling:
    def test_404_on_unknown_api(self, client: TestClient):
        r = client.get("/api/v1/nonexistent-endpoint-xyz")
        assert r.status_code == 404 or r.status_code == 405

    def test_api_prefix_returns_json(self, client: TestClient):
        r = client.get("/api/v1/process")
        # Should return JSON, not HTML
        assert "application/json" in r.headers.get("content-type", "")

    def test_health_returns_security_headers(self, client: TestClient):
        r = client.get("/health")
        # All security headers on every endpoint
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
