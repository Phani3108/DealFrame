"""Phase M end-to-end tests — Documentation, SDK & Developer Experience.

Tests:
  - Python SDK classes and methods
  - Documentation files exist and have content
  - README completeness
  - FastAPI auto-generated OpenAPI schema
"""

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")


# ── SDK Tests ────────────────────────────────────────────────────────────────

class TestSDKClient:
    """Verify the Python SDK module structure and client API."""

    def test_sdk_importable(self):
        mod = importlib.import_module("temporalos_sdk")
        assert hasattr(mod, "TemporalOSClient")
        assert hasattr(mod, "TemporalOSError")
        assert hasattr(mod, "JobResult")
        assert hasattr(mod, "AnnotationResult")

    def test_client_init_defaults(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient()
        assert c._base == "http://localhost:8000"
        assert c._api_key is None
        assert c._timeout == 30

    def test_client_init_custom(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient("http://myserver:9000/", api_key="tok-123", timeout=60)
        assert c._base == "http://myserver:9000"
        assert c._api_key == "tok-123"
        assert c._timeout == 60

    def test_headers_without_key(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient()
        h = c._headers()
        assert "Authorization" not in h
        assert h["Accept"] == "application/json"

    def test_headers_with_key(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient(api_key="my-key")
        h = c._headers()
        assert h["Authorization"] == "Bearer my-key"

    def test_upload_missing_file(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient()
        with pytest.raises(FileNotFoundError):
            c.upload("/nonexistent/video.mp4")

    def test_job_result_dataclass(self):
        from temporalos_sdk import JobResult
        j = JobResult(job_id="abc", status="completed", segments=[{"topic": "test"}])
        assert j.job_id == "abc"
        assert j.status == "completed"
        assert len(j.segments) == 1
        assert j.transcript == ""

    def test_annotation_result_dataclass(self):
        from temporalos_sdk import AnnotationResult
        a = AnnotationResult(id="a1", job_id="j1", label="objection", comment="test")
        assert a.id == "a1"
        assert a.resolved is False

    def test_error_class(self):
        from temporalos_sdk import TemporalOSError
        e = TemporalOSError("Not found", status_code=404)
        assert str(e) == "Not found"
        assert e.status_code == 404

    def test_client_methods_exist(self):
        from temporalos_sdk import TemporalOSClient
        c = TemporalOSClient()
        methods = [
            "health", "upload", "get_job", "wait_for_result", "list_jobs",
            "search", "get_objections", "get_risk_summary",
            "list_annotations", "create_annotation", "get_patterns",
            "analyze_live", "system_stats",
        ]
        for m in methods:
            assert hasattr(c, m), f"SDK missing method: {m}"
            assert callable(getattr(c, m))


# ── Documentation Tests ──────────────────────────────────────────────────────

class TestDocumentation:
    """Verify docs exist, have substance, and cover key topics."""

    @pytest.fixture
    def docs_dir(self):
        return ROOT / "docs"

    def test_deployment_guide_exists(self, docs_dir):
        f = docs_dir / "deployment.md"
        assert f.exists()
        content = f.read_text()
        assert len(content) > 500
        assert "Docker" in content or "docker" in content
        assert "DATABASE_URL" in content
        assert "health" in content.lower()

    def test_architecture_doc_exists(self, docs_dir):
        f = docs_dir / "architecture.md"
        assert f.exists()
        content = f.read_text()
        assert len(content) > 500
        assert "FastAPI" in content
        assert "Pipeline" in content or "pipeline" in content

    def test_api_reference_exists(self, docs_dir):
        f = docs_dir / "api-reference.md"
        assert f.exists()
        content = f.read_text()
        assert len(content) > 500
        assert "/api/v1/process" in content
        assert "/api/v1/search" in content
        assert "Authorization" in content

    def test_architecture_lists_all_route_modules(self, docs_dir):
        content = (docs_dir / "architecture.md").read_text()
        key_routes = ["process", "search", "intelligence", "annotations",
                      "copilot", "admin", "audit", "patterns"]
        for route in key_routes:
            assert route in content, f"Architecture doc missing route: {route}"

    def test_deployment_covers_env_vars(self, docs_dir):
        content = (docs_dir / "deployment.md").read_text()
        for var in ["DEEPGRAM_API_KEY", "STORAGE_BACKEND", "SECRET_KEY"]:
            assert var in content, f"Deployment doc missing env var: {var}"

    def test_deployment_covers_health_probes(self, docs_dir):
        content = (docs_dir / "deployment.md").read_text()
        assert "/health/live" in content
        assert "/health/ready" in content


# ── README Tests ─────────────────────────────────────────────────────────────

class TestREADME:
    """Verify README is comprehensive."""

    @pytest.fixture
    def readme(self):
        return (ROOT / "README.md").read_text()

    def test_readme_exists(self):
        assert (ROOT / "README.md").exists()

    def test_readme_has_quick_start(self, readme):
        assert "Quick Start" in readme

    def test_readme_has_docker(self, readme):
        assert "docker" in readme.lower()

    def test_readme_has_sdk_section(self, readme):
        assert "SDK" in readme or "sdk" in readme
        assert "TemporalOSClient" in readme

    def test_readme_has_documentation_links(self, readme):
        assert "architecture" in readme.lower()
        assert "deployment" in readme.lower()
        assert "api" in readme.lower()

    def test_readme_has_test_commands(self, readme):
        assert "make test" in readme


# ── OpenAPI Schema Tests ─────────────────────────────────────────────────────

class TestOpenAPI:
    """Verify FastAPI auto-generates a valid OpenAPI schema."""

    @pytest.fixture
    def client(self):
        from temporalos.api.main import app
        from httpx import AsyncClient, ASGITransport
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_openapi_schema_available(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "info" in schema

    @pytest.mark.asyncio
    async def test_openapi_has_process_paths(self, client):
        resp = await client.get("/openapi.json")
        paths = resp.json()["paths"]
        # At least the core process endpoints should be in the schema
        process_paths = [p for p in paths if "process" in p]
        assert len(process_paths) > 0

    @pytest.mark.asyncio
    async def test_openapi_has_search_path(self, client):
        resp = await client.get("/openapi.json")
        paths = resp.json()["paths"]
        search_paths = [p for p in paths if "search" in p]
        assert len(search_paths) > 0

    @pytest.mark.asyncio
    async def test_swagger_ui_available(self, client):
        resp = await client.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc_available(self, client):
        resp = await client.get("/redoc")
        assert resp.status_code == 200
