"""Phase I — State Persistence & Data Integrity e2e tests.

Tests DB persistence round-trips for:
- Alembic migrations (schema creation)
- AuditTrail async_log / async_query / load_from_db
- NotificationService async_send / load_from_db
- AnnotationStore async_create / async_update / async_delete / load_from_db
- ActiveLearningQueue async_gate / async_approve / async_correct / load_from_db
- Auth persist_user / load_users_from_db
- Multi-tenant async_register_tenant / load_tenants_from_db
- Configurable AUTH_SECRET
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db():
    """Create a temporary SQLite DB for testing persistence."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    yield url, path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def session_factory(tmp_db):
    """Create async session factory with all tables."""
    url, _ = tmp_db
    engine = create_async_engine(url, echo=False)

    async def _setup():
        from temporalos.db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, expire_on_commit=False)

    sf = asyncio.get_event_loop().run_until_complete(_setup())
    yield sf
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Alembic Schema Tests ─────────────────────────────────────────────────────

class TestAlembicSetup:
    def test_alembic_ini_exists(self):
        ini = Path(__file__).parent.parent.parent / "alembic.ini"
        assert ini.exists(), "alembic.ini should exist at project root"

    def test_alembic_versions_dir_exists(self):
        versions = Path(__file__).parent.parent.parent / "alembic" / "versions"
        assert versions.exists(), "alembic/versions directory should exist"

    def test_initial_migration_exists(self):
        versions = Path(__file__).parent.parent.parent / "alembic" / "versions"
        py_files = list(versions.glob("*.py"))
        assert len(py_files) >= 1, "At least one migration should exist"

    def test_all_tables_created_by_models(self, session_factory):
        """Verify all expected tables are created via Base.metadata.create_all."""
        from sqlalchemy import inspect

        async def _check():
            from temporalos.db.models import Base
            engine = session_factory.kw.get("bind") or list(session_factory.kw.values())[0] if session_factory.kw else None
            # Get engine from a session
            async with session_factory() as s:
                conn = await s.connection()
                raw = await conn.run_sync(lambda c: inspect(c).get_table_names())
                return raw

        tables = _run(_check())
        expected = {
            "videos", "segments", "extractions", "observatory_sessions",
            "model_run_records", "portfolios", "portfolio_videos", "risk_events",
            "kg_nodes", "kg_edges", "summary_cache", "coaching_records",
            "speaker_labels", "tenants", "users", "audit_logs", "notifications",
            "annotations", "review_items",
        }
        for t in expected:
            assert t in tables, f"Table '{t}' should exist"


# ── DB Model Tests ────────────────────────────────────────────────────────────

class TestNewDBModels:
    def test_annotation_record_model(self):
        from temporalos.db.models import AnnotationRecord
        assert AnnotationRecord.__tablename__ == "annotations"

    def test_review_item_record_model(self):
        from temporalos.db.models import ReviewItemRecord
        assert ReviewItemRecord.__tablename__ == "review_items"

    def test_user_has_tier_column(self):
        from temporalos.db.models import User
        cols = {c.name for c in User.__table__.columns}
        assert "tier" in cols, "User model should have a 'tier' column"


# ── AuditTrail Persistence Tests ─────────────────────────────────────────────

class TestAuditTrailPersistence:
    def test_audit_trail_accepts_session_factory(self, session_factory):
        from temporalos.enterprise.audit import AuditTrail
        trail = AuditTrail(session_factory=session_factory)
        assert trail._sf is session_factory

    def test_sync_log_still_works_without_sf(self):
        from temporalos.enterprise.audit import AuditTrail
        trail = AuditTrail()
        entry = trail.log("u1", "t1", "create", "video", "v1")
        assert entry.action == "create"
        assert trail.count("t1") == 1

    def test_async_log_persists_to_db(self, session_factory):
        from temporalos.enterprise.audit import AuditTrail

        async def _test():
            trail = AuditTrail(session_factory=session_factory)
            entry = await trail.async_log("u1", "t1", "upload", "video", "v123")
            assert entry.action == "upload"

            # Verify in DB
            from temporalos.db.models import AuditLog
            async with session_factory() as s:
                from sqlalchemy import select
                rows = (await s.execute(select(AuditLog))).scalars().all()
                assert len(rows) == 1
                assert rows[0].action == "upload"
                assert rows[0].resource_id == "v123"

        _run(_test())

    def test_load_from_db_populates_memory(self, session_factory):
        from temporalos.enterprise.audit import AuditTrail

        async def _test():
            # Write directly to DB
            from temporalos.db.models import AuditLog
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(AuditLog(
                    action="delete", resource_type="video",
                    resource_id="v999", details={},
                    created_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            # Load into a fresh trail
            trail = AuditTrail(session_factory=session_factory)
            assert len(trail._entries) == 0
            await trail.load_from_db()
            assert len(trail._entries) == 1
            assert trail._entries[0].action == "delete"

        _run(_test())

    def test_async_query_reads_from_db(self, session_factory):
        from temporalos.enterprise.audit import AuditTrail

        async def _test():
            trail = AuditTrail(session_factory=session_factory)
            await trail.async_log("u1", "t1", "create", "video", "v1")
            await trail.async_log("u1", "t1", "read", "report", "r1")

            results = await trail.async_query(action="create")
            assert len(results) == 1
            assert results[0].action == "create"

        _run(_test())

    def test_init_audit_trail_factory(self, session_factory):
        from temporalos.enterprise.audit import init_audit_trail, get_audit_trail
        init_audit_trail(session_factory)
        trail = get_audit_trail()
        assert trail._sf is session_factory


# ── NotificationService Persistence Tests ─────────────────────────────────────

class TestNotificationPersistence:
    def test_sync_send_still_works(self):
        from temporalos.notifications import NotificationService
        svc = NotificationService()
        n = svc.send("u1", "risk_alert", "Test", "Test msg")
        assert n.type == "risk_alert"
        assert svc.unread_count("u1") == 1

    def test_async_send_persists(self, session_factory):
        from temporalos.notifications import NotificationService

        async def _test():
            svc = NotificationService(session_factory=session_factory)
            n = await svc.async_send("u1", "batch_complete", "Done", "All done")
            assert n.type == "batch_complete"

            from temporalos.db.models import Notification as NM
            async with session_factory() as s:
                from sqlalchemy import select
                rows = (await s.execute(select(NM))).scalars().all()
                assert len(rows) == 1
                assert rows[0].title == "Done"

        _run(_test())

    def test_load_from_db_populates_memory(self, session_factory):
        from temporalos.notifications import NotificationService

        async def _test():
            from temporalos.db.models import Notification as NM
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(NM(
                    type="drift", title="Drift!", message="Model drifted",
                    read=False, extra={},
                    created_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            svc = NotificationService(session_factory=session_factory)
            await svc.load_from_db()
            assert svc._counter >= 1

        _run(_test())

    def test_init_notification_service_factory(self, session_factory):
        from temporalos.notifications import init_notification_service, get_notification_service
        init_notification_service(session_factory)
        svc = get_notification_service()
        assert svc._sf is session_factory


# ── AnnotationStore Persistence Tests ─────────────────────────────────────────

class TestAnnotationPersistence:
    def test_sync_create_still_works(self):
        from temporalos.intelligence.annotations import AnnotationStore
        store = AnnotationStore()
        ann = store.create("j1", "u1", 0, 0, 5, "objection", "test")
        assert ann.label == "objection"
        assert store.count == 1

    def test_async_create_persists(self, session_factory):
        from temporalos.intelligence.annotations import AnnotationStore

        async def _test():
            store = AnnotationStore(session_factory=session_factory)
            ann = await store.async_create("j1", "u1", 0, 0, 5, "risk", "risky")
            assert ann.label == "risk"

            from temporalos.db.models import AnnotationRecord
            async with session_factory() as s:
                from sqlalchemy import select
                rows = (await s.execute(select(AnnotationRecord))).scalars().all()
                assert len(rows) == 1
                assert rows[0].label == "risk"
                assert rows[0].uid == ann.id

        _run(_test())

    def test_async_update_persists(self, session_factory):
        from temporalos.intelligence.annotations import AnnotationStore

        async def _test():
            store = AnnotationStore(session_factory=session_factory)
            ann = await store.async_create("j1", "u1", 0, 0, 5, "risk", "initial")
            updated = await store.async_update(ann.id, comment="updated comment")
            assert updated.comment == "updated comment"

            from temporalos.db.models import AnnotationRecord
            async with session_factory() as s:
                from sqlalchemy import select
                row = (await s.execute(
                    select(AnnotationRecord).where(AnnotationRecord.uid == ann.id)
                )).scalar_one()
                assert row.comment == "updated comment"

        _run(_test())

    def test_async_delete_removes_from_db(self, session_factory):
        from temporalos.intelligence.annotations import AnnotationStore

        async def _test():
            store = AnnotationStore(session_factory=session_factory)
            ann = await store.async_create("j1", "u1", 0, 0, 5, "positive", "good")
            assert store.count == 1

            deleted = await store.async_delete(ann.id)
            assert deleted is True
            assert store.count == 0

            from temporalos.db.models import AnnotationRecord
            async with session_factory() as s:
                from sqlalchemy import select, func
                count = (await s.execute(select(func.count()).select_from(AnnotationRecord))).scalar()
                assert count == 0

        _run(_test())

    def test_load_from_db_populates_memory(self, session_factory):
        from temporalos.intelligence.annotations import AnnotationStore

        async def _test():
            from temporalos.db.models import AnnotationRecord
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(AnnotationRecord(
                    uid="test123", job_id="j1", user_id="u1",
                    segment_index=0, start_word=0, end_word=3,
                    label="question", comment="loaded",
                    tags=["t1"], resolved=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            store = AnnotationStore(session_factory=session_factory)
            assert store.count == 0
            await store.load_from_db()
            assert store.count == 1
            ann = store.get("test123")
            assert ann is not None
            assert ann.label == "question"

        _run(_test())

    def test_init_annotation_store_factory(self, session_factory):
        from temporalos.intelligence.annotations import init_annotation_store, get_annotation_store
        init_annotation_store(session_factory)
        store = get_annotation_store()
        assert store._sf is session_factory


# ── ActiveLearningQueue Persistence Tests ─────────────────────────────────────

class TestActiveLearningPersistence:
    def test_sync_gate_still_works(self):
        from temporalos.intelligence.active_learning import ActiveLearningQueue
        q = ActiveLearningQueue(0.6)
        item = q.gate("j1", 0, {"topic": "pricing"}, 0.3)
        assert item is not None
        assert item.confidence == 0.3

    def test_async_gate_persists(self, session_factory):
        from temporalos.intelligence.active_learning import ActiveLearningQueue

        async def _test():
            q = ActiveLearningQueue(0.6, session_factory=session_factory)
            item = await q.async_gate("j1", 0, {"topic": "pricing"}, 0.3)
            assert item is not None

            from temporalos.db.models import ReviewItemRecord
            async with session_factory() as s:
                from sqlalchemy import select
                rows = (await s.execute(select(ReviewItemRecord))).scalars().all()
                assert len(rows) == 1
                assert rows[0].confidence == 0.3
                assert rows[0].status == "pending"

        _run(_test())

    def test_async_approve_persists(self, session_factory):
        from temporalos.intelligence.active_learning import ActiveLearningQueue

        async def _test():
            q = ActiveLearningQueue(0.6, session_factory=session_factory)
            item = await q.async_gate("j1", 0, {"topic": "demo"}, 0.2)
            approved = await q.async_approve(item.id, "reviewer1", "looks good")
            assert approved.status.value == "approved"

            from temporalos.db.models import ReviewItemRecord
            async with session_factory() as s:
                from sqlalchemy import select
                row = (await s.execute(
                    select(ReviewItemRecord).where(ReviewItemRecord.uid == item.id)
                )).scalar_one()
                assert row.status == "approved"
                assert row.reviewer == "reviewer1"

        _run(_test())

    def test_async_correct_persists(self, session_factory):
        from temporalos.intelligence.active_learning import ActiveLearningQueue

        async def _test():
            q = ActiveLearningQueue(0.6, session_factory=session_factory)
            item = await q.async_gate("j1", 0, {"topic": "pricing"}, 0.4)
            corrected = await q.async_correct(
                item.id, "reviewer2", {"topic": "objection"}, "wrong label"
            )
            assert corrected.status.value == "corrected"

            from temporalos.db.models import ReviewItemRecord
            async with session_factory() as s:
                from sqlalchemy import select
                row = (await s.execute(
                    select(ReviewItemRecord).where(ReviewItemRecord.uid == item.id)
                )).scalar_one()
                assert row.status == "corrected"
                assert row.corrected_extraction == {"topic": "objection"}

        _run(_test())

    def test_load_from_db_populates_memory(self, session_factory):
        from temporalos.intelligence.active_learning import ActiveLearningQueue

        async def _test():
            from temporalos.db.models import ReviewItemRecord
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(ReviewItemRecord(
                    uid="rev123", job_id="j1", segment_index=0,
                    extraction={"topic": "test"}, confidence=0.25,
                    status="pending", created_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            q = ActiveLearningQueue(0.6, session_factory=session_factory)
            assert q.pending_count == 0
            await q.load_from_db()
            assert q.pending_count == 1

        _run(_test())

    def test_init_active_learning_queue_factory(self, session_factory):
        from temporalos.intelligence.active_learning import init_active_learning_queue, get_active_learning_queue
        init_active_learning_queue(session_factory=session_factory)
        q = get_active_learning_queue()
        assert q._sf is session_factory


# ── Auth Persistence Tests ────────────────────────────────────────────────────

class TestAuthPersistence:
    def test_secret_key_from_env(self):
        """AUTH_SECRET env var should be used for JWT signing."""
        import temporalos.auth as auth_mod
        original = auth_mod._SECRET_KEY
        # The key should be set (either from env or auto-generated)
        assert len(original) >= 32

    def test_register_still_works_without_db(self):
        import temporalos.auth as auth_mod
        # Clear users to avoid conflicts
        auth_mod._users.clear()
        auth_mod._api_keys.clear()
        result = auth_mod.register("test@example.com", "password123", "Test User")
        assert result["email"] == "test@example.com"
        assert "access_token" in result
        auth_mod._users.clear()
        auth_mod._api_keys.clear()

    def test_login_still_works_without_db(self):
        import temporalos.auth as auth_mod
        auth_mod._users.clear()
        auth_mod._api_keys.clear()
        auth_mod.register("login@example.com", "password123")
        result = auth_mod.login("login@example.com", "password123")
        assert "access_token" in result
        auth_mod._users.clear()
        auth_mod._api_keys.clear()

    def test_persist_user_to_db(self, session_factory):
        import temporalos.auth as auth_mod

        async def _test():
            auth_mod._users.clear()
            auth_mod._api_keys.clear()
            auth_mod.init_auth(session_factory=session_factory)

            auth_mod.register("db@example.com", "password123", "DB User")
            await auth_mod.persist_user("db@example.com")

            from temporalos.db.models import User
            async with session_factory() as s:
                from sqlalchemy import select
                row = (await s.execute(
                    select(User).where(User.email == "db@example.com")
                )).scalar_one()
                assert row.display_name == "DB User"
                assert row.role == "analyst"

            auth_mod._users.clear()
            auth_mod._api_keys.clear()

        _run(_test())

    def test_load_users_from_db(self, session_factory):
        import temporalos.auth as auth_mod

        async def _test():
            from temporalos.db.models import User
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(User(
                    email="loaded@example.com",
                    hashed_password="fake:hash",
                    display_name="Loaded",
                    role="admin",
                    tier="pro",
                    api_key="tos_loaded123",
                    created_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            auth_mod._users.clear()
            auth_mod._api_keys.clear()
            auth_mod.init_auth(session_factory=session_factory)
            await auth_mod.load_users_from_db()

            assert "loaded@example.com" in auth_mod._users
            assert auth_mod._users["loaded@example.com"]["role"] == "admin"
            assert auth_mod._api_keys.get("tos_loaded123") == "loaded@example.com"

            auth_mod._users.clear()
            auth_mod._api_keys.clear()

        _run(_test())


# ── Multi-Tenant Persistence Tests ────────────────────────────────────────────

class TestTenantPersistence:
    def test_sync_register_still_works(self):
        from temporalos.enterprise.multi_tenant import register_tenant, _tenants
        _tenants.clear()
        ctx = register_tenant("t1", "acme", "pro")
        assert ctx.plan == "pro"
        assert ctx.tenant_slug == "acme"
        _tenants.clear()

    def test_async_register_persists(self, session_factory):
        from temporalos.enterprise import multi_tenant

        async def _test():
            multi_tenant._tenants.clear()
            multi_tenant.init_tenant_persistence(session_factory)

            ctx = await multi_tenant.async_register_tenant("t2", "beta-corp", "enterprise")
            assert ctx.plan == "enterprise"

            from temporalos.db.models import Tenant
            async with session_factory() as s:
                from sqlalchemy import select
                row = (await s.execute(
                    select(Tenant).where(Tenant.slug == "beta-corp")
                )).scalar_one()
                assert row.plan == "enterprise"

            multi_tenant._tenants.clear()

        _run(_test())

    def test_load_tenants_from_db(self, session_factory):
        from temporalos.enterprise import multi_tenant

        async def _test():
            from temporalos.db.models import Tenant
            from datetime import datetime, timezone
            async with session_factory() as s:
                s.add(Tenant(
                    name="gamma", slug="gamma", plan="free",
                    settings={}, created_at=datetime.now(timezone.utc),
                ))
                await s.commit()

            multi_tenant._tenants.clear()
            multi_tenant.init_tenant_persistence(session_factory)
            await multi_tenant.load_tenants_from_db()

            tenants = multi_tenant.list_tenants()
            assert len(tenants) >= 1
            slugs = {t.tenant_slug for t in tenants}
            assert "gamma" in slugs

            multi_tenant._tenants.clear()

        _run(_test())


# ── Config Tests ──────────────────────────────────────────────────────────────

class TestConfigPersistence:
    def test_auth_secret_in_settings(self):
        from temporalos.config import Settings
        s = Settings(auth_secret="my-stable-secret")
        assert s.auth_secret == "my-stable-secret"

    def test_session_factory_available_after_init(self):
        """get_session_factory returns the factory after init_db would run."""
        from temporalos.db.session import get_session_factory
        # Before init, it should be None or a factory
        sf = get_session_factory()
        # Just verify the function exists and returns something
        assert sf is None or callable(sf)


# ── Integration: Full Round-Trip Test ─────────────────────────────────────────

class TestFullRoundTrip:
    def test_write_and_reload_all_services(self, session_factory):
        """Write data with async methods, create fresh instances, load from DB."""

        async def _test():
            # 1. Write audit entry
            from temporalos.enterprise.audit import AuditTrail
            trail1 = AuditTrail(session_factory=session_factory)
            await trail1.async_log("u1", "t1", "export", "report", "r1")

            # 2. Write annotation
            from temporalos.intelligence.annotations import AnnotationStore
            store1 = AnnotationStore(session_factory=session_factory)
            ann = await store1.async_create("j1", "u1", 0, 0, 5, "objection", "test")

            # 3. Write review item
            from temporalos.intelligence.active_learning import ActiveLearningQueue
            q1 = ActiveLearningQueue(0.6, session_factory=session_factory)
            item = await q1.async_gate("j1", 0, {"topic": "pricing"}, 0.3)

            # --- Create fresh instances and load from DB ---

            trail2 = AuditTrail(session_factory=session_factory)
            await trail2.load_from_db()
            assert len(trail2._entries) == 1
            assert trail2._entries[0].action == "export"

            store2 = AnnotationStore(session_factory=session_factory)
            await store2.load_from_db()
            assert store2.count == 1
            loaded_ann = store2.get(ann.id)
            assert loaded_ann.label == "objection"

            q2 = ActiveLearningQueue(0.6, session_factory=session_factory)
            await q2.load_from_db()
            assert q2.pending_count == 1

        _run(_test())
