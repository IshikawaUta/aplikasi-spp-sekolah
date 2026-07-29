import os
os.environ["FENRIR_DEV_MODE"] = "1"

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()



# ── Pre-import semua model agar mereka meng-cache get_db() asli ─────
# Jika tidak di-pre-import, test pertama di tiap class model akan
# meng-capture fake_get_db dari mock_db fixture, dan test-test berikutnya
# di class yang sama akan menggunakan stale closure ke mock db yang salah.

import models.audit
import models.bank_account
import models.class_model
import models.component
import models.dashboard
import models.helpers
import models.invoice
import models.payment
import models.period
import models.student
import models.user
import models.virtual_account

# ── Mock DB untuk model unit tests ───────────────────────────────────

@pytest.fixture
def mock_db(monkeypatch):
    """MagicMock database dengan semua collection method async."""

    def make_cursor(docs, default=None):
        m = AsyncMock()
        m.to_list = AsyncMock(return_value=docs if docs is not None else default or [])
        m.sort = MagicMock(return_value=m)
        m.limit = MagicMock(return_value=m)
        m.skip = MagicMock(return_value=m)
        return m

    def make_collection(name):
        col = MagicMock()
        col.name = name
        col.find = MagicMock(return_value=make_cursor([]))
        col.find_one = AsyncMock(return_value=None)
        col.count_documents = AsyncMock(return_value=0)
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        col.insert_many = AsyncMock()
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        col.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        col.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
        col.aggregate = MagicMock(return_value=make_cursor([]))
        col.create_index = AsyncMock()
        col.index_information = AsyncMock(return_value={})
        col.distinct = AsyncMock(return_value=[])
        col.find_one_and_update = AsyncMock(
            return_value={"seq": 1, "_id": name, "value": 1})
        col.find_one_and_delete = AsyncMock()
        return col

    db = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    db.list_collection_names = AsyncMock(return_value=[
        "students", "user_profiles", "classes", "components",
        "academic_years", "billing_periods", "fee_configs",
        "invoices", "payments", "payment_lines",
        "virtual_accounts", "va_invoice_lines", "bank_accounts",
        "audit_logs", "sequences",
    ])

    for name in ("students", "user_profiles", "classes", "components",
                  "academic_years", "billing_periods", "fee_configs",
                  "invoices", "payments", "payment_lines",
                  "virtual_accounts", "va_invoice_lines", "bank_accounts",
                  "audit_logs", "sequences"):
        setattr(db, name, make_collection(name))

    db.__getitem__ = lambda s, k: getattr(s, k)

    async def fake_get_db():
        return db

    monkeypatch.setattr("models.db.get_db", fake_get_db)
    monkeypatch.setattr("models.db._db", db, raising=False)

    return db


# ── FenrirTestClient untuk route tests ──────────────────────────────

class Client:
    """Sync wrapper with cookie persistence."""

    def __init__(self, app):
        from fenrir.testing import FenrirTestClient
        self._tc = FenrirTestClient(app)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._cookie = None

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def _open(self):
        self._run(self._tc.__aenter__())

    def _close(self):
        self._run(self._tc.__aexit__(None, None, None))
        self._loop.close()

    def _headers(self):
        return {"Cookie": self._cookie} if self._cookie else {}

    def get(self, url, **kw):
        kw.setdefault("headers", {}).update(self._headers())
        return self._run(self._tc.get(url, **kw))

    def post(self, url, **kw):
        kw.setdefault("headers", {}).update(self._headers())
        resp = self._run(self._tc.post(url, **kw))
        sc = resp.headers.get("set-cookie", "")
        if sc:
            self._cookie = sc.split(";")[0]
        return resp

    def login(self, email="admin@spp.sch.id", password="admin123"):
        return self.post("/auth/login", data={"email": email, "password": password})

    def db_refs(self):
        """Fetch real DB references using the client's event loop."""
        from models.db import get_db

        async def _fetch():
            db = await get_db()
            klass = await db.classes.find_one({})
            comp = await db.components.find_one({})
            period = await db.billing_periods.find_one({})
            ay = await db.academic_years.find_one({"is_active": True})
            student = await db.students.find_one({})
            return {
                "class_id": str(klass["_id"]) if klass else None,
                "component_id": str(comp["_id"]) if comp else None,
                "period_id": str(period["_id"]) if period else None,
                "ay_id": str(ay["_id"]) if ay else None,
                "student_id": str(student["_id"]) if student else None,
                "student_nis": student.get("nis", "") if student else "",
            }

        return self._run(_fetch())


@pytest.fixture(scope="module")
def client():
    from app import app
    c = Client(app)
    c._open()
    yield c
    c._close()


@pytest.fixture(scope="module")
def auth_client(client):
    r = client.login()
    assert r.status_code == 302, f"Login failed: {r.status_code}"
    return client
