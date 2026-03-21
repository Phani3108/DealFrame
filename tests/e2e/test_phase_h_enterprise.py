"""End-to-end tests for Phase H — Enterprise Scale."""
import pytest
import time


# ---------------------------------------------------------------------------
# H1  Multi-Tenant Architecture
# ---------------------------------------------------------------------------
from temporalos.enterprise.multi_tenant import (
    TenantContext, register_tenant, get_tenant_by_id, get_tenant_by_slug,
    set_tenant, get_tenant, require_tenant, tenant_filter, list_tenants,
    _tenants,
)


class TestMultiTenant:
    def setup_method(self):
        _tenants.clear()

    def test_register_and_get(self):
        ctx = register_tenant("t1", "acme", "pro")
        assert ctx.tenant_id == "t1"
        assert get_tenant_by_id("t1") is ctx
        assert get_tenant_by_slug("acme") is ctx

    def test_duplicate_slug_raises(self):
        register_tenant("t1", "acme")
        with pytest.raises(ValueError, match="already exists"):
            register_tenant("t2", "acme")

    def test_context_var(self):
        ctx = TenantContext("t1", "acme", "enterprise")
        set_tenant(ctx)
        assert get_tenant() is ctx
        assert require_tenant() is ctx

    def test_require_tenant_raises(self):
        set_tenant(None)
        with pytest.raises(PermissionError):
            require_tenant()

    def test_plan_limits(self):
        ctx = TenantContext("t1", "test", "free")
        assert ctx.max_videos == 10
        assert ctx.max_users == 3
        ent = TenantContext("t2", "ent", "enterprise")
        assert ent.max_videos == 10000
        assert ent.is_enterprise

    def test_tenant_filter(self):
        items = [
            {"id": 1, "tenant_id": "t1"},
            {"id": 2, "tenant_id": "t2"},
            {"id": 3, "tenant_id": "t1"},
        ]
        filtered = tenant_filter(items, tenant_id="t1")
        assert len(filtered) == 2

    def test_list_tenants(self):
        register_tenant("t1", "alpha")
        register_tenant("t2", "beta")
        assert len(list_tenants()) == 2


# ---------------------------------------------------------------------------
# H2  SSO Providers
# ---------------------------------------------------------------------------
from temporalos.enterprise.sso import (
    GoogleSSO, MicrosoftSSO, OktaSSO, SSOUser, get_sso_provider,
)


class TestSSO:
    def test_google_authorize_url(self):
        sso = GoogleSSO("client_id", "secret", "https://example.com/callback")
        url = sso.authorize_url("state123")
        assert "accounts.google.com" in url
        assert "client_id" in url
        assert "state123" in url

    def test_microsoft_authorize_url(self):
        sso = MicrosoftSSO("client_id", "secret", "https://example.com/callback")
        url = sso.authorize_url("state456")
        assert "login.microsoftonline.com" in url
        assert "client_id" in url

    def test_okta_authorize_url(self):
        sso = OktaSSO("client_id", "secret", "https://example.com/callback",
                       okta_domain="https://myorg.okta.com")
        url = sso.authorize_url()
        assert "myorg.okta.com" in url

    def test_google_parse_userinfo(self):
        user = GoogleSSO.parse_userinfo({
            "id": "123", "email": "test@example.com",
            "name": "Test User", "picture": "https://example.com/pic.jpg",
        })
        assert isinstance(user, SSOUser)
        assert user.provider == "google"
        assert user.email == "test@example.com"

    def test_microsoft_parse_userinfo(self):
        user = MicrosoftSSO.parse_userinfo({
            "id": "456", "mail": "user@corp.com", "displayName": "Corp User",
        })
        assert user.provider == "microsoft"
        assert user.email == "user@corp.com"

    def test_factory(self):
        sso = get_sso_provider("google", client_id="id", client_secret="s",
                               redirect_uri="http://localhost")
        assert isinstance(sso, GoogleSSO)

    def test_factory_unknown(self):
        with pytest.raises(ValueError, match="Unknown SSO"):
            get_sso_provider("unknown", client_id="", client_secret="",
                             redirect_uri="")


# ---------------------------------------------------------------------------
# H3  RBAC
# ---------------------------------------------------------------------------
from temporalos.enterprise.rbac import (
    has_permission, check_permission, list_roles, list_permissions_for_role,
    RBACPolicy,
)


class TestRBAC:
    def test_admin_has_all(self):
        assert has_permission("admin", "video", "create")
        assert has_permission("admin", "tenant", "admin")
        assert has_permission("admin", "users", "delete")

    def test_viewer_limited(self):
        assert has_permission("viewer", "video", "read")
        assert not has_permission("viewer", "video", "create")
        assert not has_permission("viewer", "users", "delete")

    def test_analyst_permissions(self):
        assert has_permission("analyst", "extraction", "read")
        assert has_permission("analyst", "export", "create")
        assert not has_permission("analyst", "users", "create")

    def test_check_raises(self):
        with pytest.raises(PermissionError):
            check_permission("viewer", "video", "delete")

    def test_list_roles(self):
        roles = list_roles()
        assert "admin" in roles
        assert "viewer" in roles

    def test_custom_policy(self):
        policy = RBACPolicy(tenant_id="t1")
        policy.add_custom_role("intern", ["video:read", "extraction:read"])
        assert policy.has_permission("intern", "video", "read")
        assert not policy.has_permission("intern", "video", "create")

    def test_policy_falls_back(self):
        policy = RBACPolicy(tenant_id="t1")
        assert policy.has_permission("admin", "video", "create")


# ---------------------------------------------------------------------------
# H4  Task Queue
# ---------------------------------------------------------------------------
from temporalos.enterprise.task_queue import TaskQueue, TaskStatus


class TestTaskQueue:
    def test_submit_and_execute(self):
        q = TaskQueue()
        q.register_handler("add", lambda a, b: a + b)
        task = q.submit("add", {"a": 2, "b": 3})
        assert task.status == TaskStatus.PENDING
        q.execute(task.id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 5

    def test_no_handler_fails(self):
        q = TaskQueue()
        task = q.submit("unknown", {})
        q.execute(task.id)
        assert task.status == TaskStatus.FAILED
        assert "No handler" in task.error

    def test_process_all(self):
        q = TaskQueue()
        q.register_handler("echo", lambda msg: msg)
        q.submit("echo", {"msg": "hello"})
        q.submit("echo", {"msg": "world"})
        results = q.process_all()
        assert len(results) == 2
        assert all(t.status == TaskStatus.COMPLETED for t in results)

    def test_priority_ordering(self):
        q = TaskQueue()
        order = []
        q.register_handler("track", lambda label: order.append(label))
        q.submit("track", {"label": "low"}, priority=1)
        q.submit("track", {"label": "high"}, priority=10)
        q.submit("track", {"label": "mid"}, priority=5)
        q.process_all()
        assert order == ["high", "mid", "low"]

    def test_cancel(self):
        q = TaskQueue()
        task = q.submit("anything", {})
        assert q.cancel(task.id) is True
        assert task.status == TaskStatus.CANCELLED

    def test_metrics(self):
        q = TaskQueue()
        q.register_handler("noop", lambda: None)
        q.submit("noop", {})
        q.process_all()
        m = q.metrics()
        assert m["total_tasks"] == 1
        assert m["status_counts"]["completed"] == 1

    def test_handler_exception(self):
        q = TaskQueue()
        q.register_handler("fail", lambda: 1 / 0)
        task = q.submit("fail", {})
        q.execute(task.id)
        assert task.status == TaskStatus.FAILED
        assert "division by zero" in task.error


# ---------------------------------------------------------------------------
# H5  PII Redaction
# ---------------------------------------------------------------------------
from temporalos.enterprise.pii_redaction import (
    detect_pii, redact_text, mask_text, redact_intel,
)


class TestPIIRedaction:
    def test_detect_email(self):
        dets = detect_pii("Contact john@example.com for details")
        assert any(d.type == "email" for d in dets)

    def test_detect_phone(self):
        dets = detect_pii("Call 555-123-4567 today")
        assert any(d.type == "phone" for d in dets)

    def test_detect_ssn(self):
        dets = detect_pii("SSN is 123-45-6789")
        assert any(d.type == "ssn" for d in dets)

    def test_redact_text(self):
        redacted, dets = redact_text("Email me at test@example.com please")
        assert "[EMAIL]" in redacted
        assert "test@example.com" not in redacted

    def test_mask_text(self):
        masked, dets = mask_text("Email me at test@example.com please")
        assert "test@example.com" not in masked
        assert "**" in masked  # partial masking

    def test_no_pii(self):
        redacted, dets = redact_text("Just a normal sentence about weather")
        assert dets == []
        assert redacted == "Just a normal sentence about weather"

    def test_redact_intel(self):
        intel = {"segments": [
            {"transcript": "Contact john@example.com",
             "extraction": {"topic": "Email john@example.com",
                            "objections": ["call 555-123-4567"],
                            "decision_signals": []}},
        ]}
        redacted = redact_intel(intel)
        assert "[EMAIL]" in redacted["segments"][0]["transcript"]
        assert redacted["pii_redaction"]["redacted"] is True

    def test_detect_credit_card(self):
        dets = detect_pii("Card: 4111-1111-1111-1111")
        assert any(d.type == "credit_card" for d in dets)

    def test_detect_ip(self):
        dets = detect_pii("Server at 192.168.1.100")
        assert any(d.type == "ip_address" for d in dets)


# ---------------------------------------------------------------------------
# H6  Audit Trail
# ---------------------------------------------------------------------------
from temporalos.enterprise.audit import AuditTrail, AuditEntry


class TestAuditTrail:
    def test_log_and_query(self):
        trail = AuditTrail()
        trail.log("user1", "t1", "create", "video", "v1")
        trail.log("user1", "t1", "read", "video", "v1")
        entries = trail.query(user_id="user1")
        assert len(entries) == 2

    def test_query_by_action(self):
        trail = AuditTrail()
        trail.log("u1", "t1", "create", "video")
        trail.log("u1", "t1", "delete", "video")
        trail.log("u1", "t1", "create", "extraction")
        creates = trail.query(action="create")
        assert len(creates) == 2

    def test_query_by_tenant(self):
        trail = AuditTrail()
        trail.log("u1", "t1", "read", "video")
        trail.log("u2", "t2", "read", "video")
        assert len(trail.query(tenant_id="t1")) == 1

    def test_count(self):
        trail = AuditTrail()
        trail.log("u1", "t1", "read", "video")
        trail.log("u1", "t1", "read", "video")
        assert trail.count() == 2
        assert trail.count(tenant_id="t1") == 2
        assert trail.count(tenant_id="t_other") == 0

    def test_clear(self):
        trail = AuditTrail()
        trail.log("u1", "t1", "read", "video")
        trail.log("u2", "t2", "read", "video")
        cleared = trail.clear(tenant_id="t1")
        assert cleared == 1
        assert trail.count() == 1

    def test_entry_to_dict(self):
        trail = AuditTrail()
        entry = trail.log("u1", "t1", "export", "extraction", "e1",
                          details={"format": "csv"}, ip_address="10.0.0.1")
        d = entry.to_dict()
        assert d["action"] == "export"
        assert d["ip_address"] == "10.0.0.1"


# ---------------------------------------------------------------------------
# H7  Helm (verify files exist / parseable)
# ---------------------------------------------------------------------------
import os
import yaml


class TestHelmChart:
    HELM_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "helm", "temporalos")

    def test_chart_yaml_exists(self):
        path = os.path.join(self.HELM_DIR, "Chart.yaml")
        assert os.path.exists(path)
        with open(path) as f:
            chart = yaml.safe_load(f)
        assert chart["name"] == "temporalos"

    def test_values_yaml_exists(self):
        path = os.path.join(self.HELM_DIR, "values.yaml")
        assert os.path.exists(path)
        with open(path) as f:
            values = yaml.safe_load(f)
        assert values["replicaCount"] >= 1

    def test_deployment_template_exists(self):
        path = os.path.join(self.HELM_DIR, "templates", "deployment.yaml")
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# H8  Performance
# ---------------------------------------------------------------------------
from temporalos.enterprise.performance import TTLCache, cached, batch_process, cache_key


class TestPerformance:
    def test_ttl_cache_get_set(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("k1", "v1")
        assert c.get("k1") == "v1"

    def test_ttl_expiry(self):
        c = TTLCache(max_size=10, ttl_seconds=0.01)
        c.set("k1", "v1")
        time.sleep(0.02)
        assert c.get("k1") is None

    def test_cache_eviction(self):
        c = TTLCache(max_size=2, ttl_seconds=60)
        c.set("k1", "v1")
        c.set("k2", "v2")
        c.set("k3", "v3")
        assert len(c._cache) <= 2

    def test_cache_stats(self):
        c = TTLCache()
        c.set("k1", "v1")
        c.get("k1")  # hit
        c.get("k2")  # miss
        stats = c.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cached_decorator(self):
        call_count = 0

        @cached(ttl=60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert expensive(5) == 10  # cached
        assert call_count == 1

    def test_batch_process(self):
        results = batch_process([1, 2, 3, 4, 5], 2, lambda batch: [x * 2 for x in batch])
        assert results == [2, 4, 6, 8, 10]

    def test_cache_key_deterministic(self):
        k1 = cache_key("func", 1, 2, a="b")
        k2 = cache_key("func", 1, 2, a="b")
        assert k1 == k2
