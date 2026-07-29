"""Comprehensive unit tests dengan mock get_db()."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from bson import ObjectId


def _mock_find_one(mock_db, col, doc):
    mock_db.__getattr__(col).find_one = AsyncMock(return_value=doc)


def _mock_find(mock_db, col, docs):
    m = AsyncMock()
    m.to_list = AsyncMock(return_value=docs)
    m.sort = MagicMock(return_value=m)
    mock_db.__getattr__(col).find = MagicMock(return_value=m)


def _mock_insert_one(mock_db, col, oid):
    mock_db.__getattr__(col).insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=oid))


def _mock_count(mock_db, col, count):
    mock_db.__getattr__(col).count_documents = AsyncMock(return_value=count)


# ── Pure sync tests ──────────────────────────────────────────────────

class TestPassword:
    def test_validate_strong(self):
        from models.user import validate_password_strength
        validate_password_strength("Str0ng!Pass")

    def test_short_raises(self):
        from models.user import validate_password_strength
        with pytest.raises(ValueError, match="8 karakter"):
            validate_password_strength("Ab1!")

    def test_no_number_raises(self):
        from models.user import validate_password_strength
        with pytest.raises(ValueError, match="angka"):
            validate_password_strength("OnlyUpper!")

    def test_no_uppercase_raises(self):
        from models.user import validate_password_strength
        with pytest.raises(ValueError, match="huruf besar"):
            validate_password_strength("lowercase1")


class TestBcrypt:
    def test_hash_format(self):
        from models.user import hash_password
        h = hash_password("TestPass1!")
        assert h.startswith("$2")

    def test_verify_ok(self):
        from models.user import hash_password, verify_password
        pw = "MyTestPass123!"
        assert verify_password(pw, hash_password(pw))

    def test_verify_fail(self):
        from models.user import hash_password, verify_password
        assert not verify_password("wrong", hash_password("correct1!"))


class TestCSRF:
    def test_generate_token(self):
        from services.csrf import generate_csrf_token
        t = generate_csrf_token()
        assert len(t) == 64
        assert all(c in "0123456789abcdef" for c in t)

    def test_unique_tokens(self):
        from services.csrf import generate_csrf_token
        tokens = {generate_csrf_token() for _ in range(50)}
        assert len(tokens) == 50

    def test_get_or_create_new(self):
        from services.csrf import get_or_create_csrf_token
        s = MagicMock()
        s.get.return_value = None
        t = get_or_create_csrf_token(s)
        assert len(t) == 64

    def test_get_or_create_existing(self):
        from services.csrf import get_or_create_csrf_token
        s = MagicMock()
        s.get.return_value = "existing"
        assert get_or_create_csrf_token(s) == "existing"

    def test_validate_empty(self):
        from services.csrf import validate_csrf_token
        s = MagicMock()
        s.get.return_value = None
        assert not validate_csrf_token(s, {})

    def test_validate_mismatch(self):
        from services.csrf import validate_csrf_token
        s = MagicMock()
        s.get.return_value = "correct"
        assert not validate_csrf_token(s, {"_csrf_token": "wrong"})

    def test_validate_match(self):
        from services.csrf import validate_csrf_token
        s = MagicMock()
        s.get.return_value = "exact"
        assert validate_csrf_token(s, {"_csrf_token": "exact"})


class TestRateLimit:
    def test_not_blocked(self):
        from services.ratelimit import check_rate_limit
        assert check_rate_limit("ip_init")

    def test_max_blocks(self):
        from services.ratelimit import check_rate_limit
        ip = "ip_block"
        for _ in range(5):
            check_rate_limit(ip)
        assert not check_rate_limit(ip)


class TestObjectId:
    def test_valid(self):
        oid = ObjectId("507f1f77bcf86cd799439011")
        assert str(oid) == "507f1f77bcf86cd799439011"

    def test_invalid(self):
        from bson.errors import InvalidId
        with pytest.raises(InvalidId):
            ObjectId("bad")


class TestDummyVA:
    def test_returns_dict(self):
        from models.virtual_account import _create_dummy_va
        va = _create_dummy_va("bca", "ext_test")
        assert va["bank"] == "bca"
        assert len(va["va_number"]) >= 10

    def test_multiple_banks(self):
        from models.virtual_account import _create_dummy_va
        for bank in ("bca", "bni", "bri", "mandiri"):
            va = _create_dummy_va(bank, bank)
            assert va["bank"] == bank


class TestConfig:
    def test_keys(self):
        from config import Config
        assert len(Config.SECRET_KEY) >= 10
        assert Config.MONGO_URI.startswith("mongodb")
        assert Config.XENDIT_API_URL == "https://api.xendit.co"

    def test_dev_mode(self):
        import os
        assert os.getenv("FENRIR_DEV_MODE") == "1"


class TestFileStructure:
    def test_gitignore(self):
        with open(".gitignore") as f:
            assert ".env" in f.read()

    def test_requirements(self):
        with open("requirements.txt") as f:
            reqs = f.read()
        for pkg in ("fenrir-framework", "motor", "bcrypt", "openpyxl"):
            assert pkg in reqs


# ── Model tests dengan mock DB ───────────────────────────────────────

class TestGetUsers:
    async def test_returns_list(self, mock_db):
        from models.user import get_users
        _mock_find(mock_db, "user_profiles", [{"email": "a@b.com"}])
        users = await get_users()
        assert len(users) == 1

    async def test_empty(self, mock_db):
        from models.user import get_users
        _mock_find(mock_db, "user_profiles", [])
        users = await get_users()
        assert users == []


class TestGetUserById:
    async def test_found(self, mock_db):
        from models.user import get_user_by_id
        oid = ObjectId()
        _mock_find_one(mock_db, "user_profiles", {"_id": oid, "email": "x@y.com"})
        user = await get_user_by_id(str(oid))
        assert user["email"] == "x@y.com"

    async def test_not_found(self, mock_db):
        from models.user import get_user_by_id
        _mock_find_one(mock_db, "user_profiles", None)
        user = await get_user_by_id(str(ObjectId()))
        assert user is None


class TestToggleUserActive:
    async def test_toggle(self, mock_db):
        from models.user import toggle_user_active
        oid = ObjectId()
        mock_db.user_profiles.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await toggle_user_active(str(oid), False)
        assert result is True


class TestUpdateUserRole:
    async def test_change_role(self, mock_db):
        from models.user import update_user_role
        oid = ObjectId()
        mock_db.user_profiles.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_user_role(str(oid), "admin")
        assert result is True


class TestUpdateUserPassword:
    async def test_change_password(self, mock_db):
        from models.user import update_user_password
        oid = ObjectId()
        mock_db.user_profiles.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_user_password(str(oid), "NewSecure1!")
        assert result is True


class TestCreateUser:
    async def test_create(self, mock_db):
        from models.user import create_user
        oid = ObjectId()
        _mock_insert_one(mock_db, "user_profiles", oid)
        result = await create_user("new@test.com", "New User", "Str0ng!Pass")
        assert result is not None


class TestAuthenticateUser:
    async def test_valid(self, mock_db):
        from models.user import authenticate, hash_password
        hashed = hash_password("pass123")
        _mock_find_one(mock_db, "user_profiles", {
            "email": "admin@test.com", "password_hash": hashed,
            "role": "admin", "is_active": True,
        })
        user = await authenticate("admin@test.com", "pass123")
        assert user is not None
        assert user["role"] == "admin"

    async def test_wrong_password(self, mock_db):
        from models.user import authenticate, hash_password
        _mock_find_one(mock_db, "user_profiles", {
            "email": "admin@test.com", "password_hash": hash_password("correct"),
            "is_active": True,
        })
        user = await authenticate("admin@test.com", "wrong")
        assert user is None

    async def test_inactive(self, mock_db):
        from models.user import authenticate, hash_password
        _mock_find_one(mock_db, "user_profiles", {
            "email": "admin@test.com", "password_hash": hash_password("pass123"),
            "is_active": False,
        })
        user = await authenticate("admin@test.com", "pass123")
        assert user is None

    async def test_not_found(self, mock_db):
        from models.user import authenticate
        _mock_find_one(mock_db, "user_profiles", None)
        user = await authenticate("x@x.com", "any")
        assert user is None


class TestStudentModel:
    async def test_get_students(self, mock_db):
        from models.student import get_students
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{"nis": "001", "class_name": "X-A"}])
        mock_db.students.aggregate = MagicMock(return_value=cursor)
        s = await get_students(search="001")
        assert len(s) == 1
        s2 = await get_students(class_id=str(ObjectId()))
        assert len(s2) == 1
        s3 = await get_students()
        assert len(s3) == 1

    async def test_get_student_by_id(self, mock_db):
        from models.student import get_student_by_id
        oid = ObjectId()
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[
            {"_id": oid, "nis": "001", "class_name": "X-A"}
        ])
        mock_db.students.aggregate = MagicMock(return_value=cursor)
        s = await get_student_by_id(str(oid))
        assert s["nis"] == "001"

    async def test_delete_student(self, mock_db):
        from models.student import delete_student
        oid = ObjectId()
        result = await delete_student(str(oid))
        assert result is True

    async def test_create_student(self, mock_db):
        from models.student import create_student
        oid = ObjectId()
        mock_db.students.find_one = AsyncMock(return_value=None)
        _mock_insert_one(mock_db, "students", oid)
        sid = await create_student({
            "nis": "NEW001", "name": "New", "angkatan": 2026, "gender": "L",
            "class_id": str(ObjectId()),
        })
        assert sid is not None

    async def test_create_student_duplicate(self, mock_db):
        from models.student import create_student
        mock_db.students.find_one = AsyncMock(return_value={"nis": "DUP001"})
        with pytest.raises(ValueError):
            await create_student({
                "nis": "DUP001", "name": "Dup", "angkatan": 2026, "gender": "L",
                "class_id": str(ObjectId()),
            })

    async def test_update_student_not_modified(self, mock_db):
        from models.student import update_student
        oid = ObjectId()
        mock_db.students.update_one = AsyncMock(
            return_value=MagicMock(modified_count=0))
        result = await update_student(str(oid), {
            "name": "Updated", "nis": "001", "angkatan": 2026,
            "gender": "L", "class_id": str(ObjectId()),
        })
        assert result is False

    async def test_update_student(self, mock_db):
        from models.student import update_student
        oid = ObjectId()
        mock_db.students.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_student(str(oid), {
            "name": "Updated", "nis": "001", "angkatan": 2026,
            "gender": "L", "class_id": str(ObjectId()),
        })
        assert result is True


class TestClassModel:
    async def test_get_classes(self, mock_db):
        from models.class_model import get_classes
        _mock_find(mock_db, "classes", [{"name": "X-A"}])
        c = await get_classes()
        assert len(c) == 1

    async def test_get_class_by_id(self, mock_db):
        from models.class_model import get_class_by_id
        oid = ObjectId()
        _mock_find_one(mock_db, "classes", {"_id": oid, "name": "X-B"})
        c = await get_class_by_id(str(oid))
        assert c["name"] == "X-B"

    async def test_create_class(self, mock_db):
        from models.class_model import create_class
        oid = ObjectId()
        _mock_insert_one(mock_db, "classes", oid)
        cid = await create_class({"name": "X-C", "jenjang": "SMK", "angkatan": 2026})
        assert cid is not None

    async def test_update_class(self, mock_db):
        from models.class_model import update_class
        oid = ObjectId()
        mock_db.classes.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_class(str(oid), {
            "name": "X-D", "jenjang": "SMK", "angkatan": 2026})
        assert result is True

    async def test_get_classes_with_filter(self, mock_db):
        from models.class_model import get_classes
        _mock_find(mock_db, "classes", [{"name": "X-A", "academic_year_id": ObjectId()}])
        c = await get_classes(academic_year_id=str(ObjectId()))
        assert len(c) == 1

    async def test_delete_class(self, mock_db):
        from models.class_model import delete_class
        oid = ObjectId()
        result = await delete_class(str(oid))
        assert result is True


class TestComponentModel:
    async def test_get_components_all(self, mock_db):
        from models.component import get_components
        _mock_find(mock_db, "components", [
            {"name": "SPP", "payment_type": "bulanan", "is_active": True},
            {"name": "BANGUNAN", "payment_type": "tahunan", "is_active": False},
        ])
        c = await get_components(active_only=False)
        assert len(c) == 2

    async def test_create_component_inactive(self, mock_db):
        from models.component import create_component
        oid = ObjectId()
        _mock_insert_one(mock_db, "components", oid)
        cid = await create_component({
            "name": "DORMANT", "payment_type": "tahunan",
            "default_amount": 100000, "is_active": False,
        })
        assert cid is not None

    async def test_get_component_by_id(self, mock_db):
        from models.component import get_component_by_id
        oid = ObjectId()
        _mock_find_one(mock_db, "components", {"_id": oid, "name": "SPP"})
        c = await get_component_by_id(str(oid))
        assert c["name"] == "SPP"

    async def test_create_component(self, mock_db):
        from models.component import create_component
        oid = ObjectId()
        _mock_insert_one(mock_db, "components", oid)
        cid = await create_component({
            "name": "UANG BANGUNAN", "payment_type": "tahunan",
            "default_amount": 500000, "is_active": True,
        })
        assert cid is not None

    async def test_update_component(self, mock_db):
        from models.component import update_component
        oid = ObjectId()
        mock_db.components.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_component(str(oid), {
            "name": "SPP", "payment_type": "bulanan",
            "default_amount": 200000, "is_active": True,
        })
        assert result is True

    async def test_delete_component(self, mock_db):
        from models.component import delete_component
        oid = ObjectId()
        result = await delete_component(str(oid))
        assert result is True


class TestInvoiceModel:
    async def test_get_invoices(self, mock_db):
        from models.invoice import get_invoices
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{"total_amount": 150000}])
        mock_db.invoices.aggregate = MagicMock(return_value=cursor)
        inv = await get_invoices()
        assert len(inv) == 1

    async def test_get_invoice_by_id(self, mock_db):
        from models.invoice import get_invoice_by_id
        oid = ObjectId()
        _mock_find_one(mock_db, "invoices", {"_id": oid, "total_amount": 150000})
        inv = await get_invoice_by_id(str(oid))
        assert inv["total_amount"] == 150000

    async def test_create_invoice(self, mock_db):
        from models.invoice import create_invoice
        oid = ObjectId()
        _mock_insert_one(mock_db, "invoices", oid)
        iid = await create_invoice({
            "student_id": str(ObjectId()), "component_id": str(ObjectId()),
            "period_id": str(ObjectId()), "total_amount": 150000,
        })
        assert iid is not None

    async def test_mass_generate_invoices(self, mock_db):
        from models.invoice import mass_generate_invoices
        sid = ObjectId()
        cid = ObjectId()
        cursor_s = AsyncMock()
        cursor_s.to_list = AsyncMock(
            return_value=[{"_id": sid, "class_id": cid, "angkatan": 2025}])
        mock_db.students.find = MagicMock(return_value=cursor_s)

        cursor_c = AsyncMock()
        cursor_c.to_list = AsyncMock(
            return_value=[{"_id": ObjectId(), "name": "SPP", "payment_type": "bulanan"}])
        mock_db.components.find = MagicMock(return_value=cursor_c)

        cursor_f = AsyncMock()
        cursor_f.to_list = AsyncMock(return_value=[
            {"component_id": ObjectId(), "angkatan": 2025, "amount": 150000}])
        mock_db.fee_configs.find = MagicMock(return_value=cursor_f)

        cursor_e = AsyncMock()
        cursor_e.to_list = AsyncMock(return_value=[])
        mock_db.invoices.find = MagicMock(return_value=cursor_e)

        mock_db.invoices.insert_many = AsyncMock(
            return_value=MagicMock(inserted_ids=[ObjectId()]))
        result = await mass_generate_invoices(
            [str(cid)], [str(ObjectId())], str(ObjectId()), str(ObjectId()))
        assert result is not None

    async def test_mass_generate_with_existing(self, mock_db):
        from models.invoice import mass_generate_invoices
        sid = ObjectId()
        cid = ObjectId()
        cid2 = ObjectId()

        cursor_s = AsyncMock()
        cursor_s.to_list = AsyncMock(
            return_value=[{"_id": sid, "class_id": cid, "angkatan": 2025}])
        mock_db.students.find = MagicMock(return_value=cursor_s)

        cursor_c = AsyncMock()
        cursor_c.to_list = AsyncMock(return_value=[
            {"_id": cid2, "name": "SPP", "payment_type": "bulanan"},
        ])
        mock_db.components.find = MagicMock(return_value=cursor_c)

        cursor_f = AsyncMock()
        cursor_f.to_list = AsyncMock(return_value=[
            {"component_id": cid2, "angkatan": 2025, "amount": 150000},
        ])
        mock_db.fee_configs.find = MagicMock(return_value=cursor_f)

        cursor_e = AsyncMock()
        cursor_e.to_list = AsyncMock(return_value=[
            {"_id": ObjectId(), "student_id": sid, "component_id": cid2,
             "period_id": ObjectId(), "status": "draft"},
        ])
        mock_db.invoices.find = MagicMock(return_value=cursor_e)

        mock_db.invoices.insert_many = AsyncMock(
            return_value=MagicMock(inserted_ids=[]))
        result = await mass_generate_invoices(
            [str(cid)], [str(cid2)], str(ObjectId()), str(ObjectId()))
        assert result is not None

    async def test_update_invoice(self, mock_db):
        from models.invoice import update_invoice
        oid = ObjectId()
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_invoice(str(oid), {"status": "paid"})
        assert result is True

    async def test_cancel_invoice(self, mock_db):
        from models.invoice import cancel_invoice
        oid = ObjectId()
        result = await cancel_invoice(str(oid))
        assert result is True

    async def test_update_invoice_paid_off(self, mock_db):
        from models.invoice import update_invoice_paid_off
        oid = ObjectId()
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_invoice_paid_off(str(oid), "2025-07-29")
        assert result is True


class TestPaymentModel:
    async def test_get_payments(self, mock_db):
        from models.payment import get_payments
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{"payment_no": "PAY-001"}])
        mock_db.payments.aggregate = MagicMock(return_value=cursor)
        p = await get_payments()
        assert len(p) == 1

    async def test_get_payment_by_id(self, mock_db):
        from models.payment import get_payment_by_id
        oid = ObjectId()
        _mock_find_one(mock_db, "payments", {
            "_id": oid, "payment_no": "PAY-001",
            "payment_date": "2025-07-01", "amount_paid": 150000,
        })
        p = await get_payment_by_id(str(oid))
        assert p["payment_no"] == "PAY-001"

    async def test_create_payment(self, mock_db):
        from models.payment import create_payment
        oid = ObjectId()
        inv_oid = ObjectId()
        _mock_insert_one(mock_db, "payments", oid)
        mock_db.payment_lines.insert_many = AsyncMock()
        mock_db.invoices.find_one = AsyncMock(return_value={
            "_id": inv_oid, "total_amount": 150000, "paid_amount": 0,
        })
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        mock_db.sequences.find_one_and_update = AsyncMock(
            return_value={"seq": 42, "_id": "payment"})
        pid = await create_payment(
            {"student_id": str(ObjectId()), "amount_paid": 150000,
             "payment_date": "2025-07-29T00:00:00"},
            [{"invoice_id": str(inv_oid), "amount_paid": 150000}],
        )
        assert pid is not None

    async def test_create_payment_partial(self, mock_db):
        from models.payment import create_payment
        oid = ObjectId()
        inv_oid = ObjectId()
        _mock_insert_one(mock_db, "payments", oid)
        mock_db.payment_lines.insert_many = AsyncMock()
        mock_db.invoices.find_one = AsyncMock(return_value={
            "_id": inv_oid, "total_amount": 150000, "paid_amount": 0,
        })
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        mock_db.sequences.find_one_and_update = AsyncMock(
            return_value={"seq": 43, "_id": "payment"})
        pid = await create_payment(
            {"student_id": str(ObjectId()), "amount_paid": 50000,
             "payment_date": "2025-07-29"},
            [{"invoice_id": str(inv_oid), "amount_paid": 50000}],
        )
        assert pid is not None

    async def test_void_payment_with_lines(self, mock_db):
        from models.payment import void_payment
        oid = ObjectId()
        inv_oid = ObjectId()
        _mock_find_one(mock_db, "payments", {
            "_id": oid, "is_voided": False, "amount_paid": 150000,
        })
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[
            {"payment_id": oid, "invoice_id": inv_oid, "amount_paid": 50000},
        ])
        mock_db.payment_lines.find = MagicMock(return_value=cursor)
        mock_db.invoices.find_one = AsyncMock(return_value={
            "_id": inv_oid, "total_amount": 150000, "paid_amount": 50000,
            "status": "posted",
        })
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(matched_count=1))
        result = await void_payment(str(oid), "test reason", "admin")
        assert result is True

    async def test_void_payment_already_voided(self, mock_db):
        from models.payment import void_payment
        oid = ObjectId()
        _mock_find_one(mock_db, "payments", {
            "_id": oid, "is_voided": True, "amount_paid": 150000,
        })
        result = await void_payment(str(oid), "test", "admin")
        assert result is False

    async def test_void_payment_not_found(self, mock_db):
        from models.payment import void_payment
        _mock_find_one(mock_db, "payments", None)
        result = await void_payment(str(ObjectId()), "test", "admin")
        assert result is False

    async def test_get_payments_with_filters(self, mock_db):
        from models.payment import get_payments
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(
            return_value=[{"payment_no": "PAY-001", "student_name": "Test"}])
        mock_db.payments.aggregate = MagicMock(return_value=cursor)
        p = await get_payments({"student_id": str(ObjectId()), "status": "paid"})
        assert len(p) == 1

    async def test_get_payments_empty(self, mock_db):
        from models.payment import get_payments
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[])
        mock_db.payments.aggregate = MagicMock(return_value=cursor)
        p = await get_payments()
        assert p == []

    async def test_get_payment_lines(self, mock_db, monkeypatch):
        from models.payment import get_payment_lines
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[
            {"amount_paid": 50000, "invoice_id": str(ObjectId()), "invoice": {}},
        ])
        monkeypatch.setattr(mock_db.payment_lines, "aggregate",
                            MagicMock(return_value=cursor))
        lines = await get_payment_lines(str(ObjectId()))
        assert len(lines) == 1


class TestVirtualAccountModel:
    def test_create_dummy_va(self):
        from models.virtual_account import _create_dummy_va
        va = _create_dummy_va("bca", "ext_test")
        assert va["bank"] == "bca"
        assert len(va["va_number"]) >= 10

    async def test_get_virtual_accounts(self, mock_db):
        from models.virtual_account import get_virtual_accounts
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{"bank_code": "bca"}])
        mock_db.virtual_accounts.aggregate = MagicMock(return_value=cursor)
        v = await get_virtual_accounts()
        assert len(v) == 1

    async def test_get_virtual_accounts_filtered(self, mock_db):
        from models.virtual_account import get_virtual_accounts
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{"bank_code": "bca"}])
        mock_db.virtual_accounts.aggregate = MagicMock(return_value=cursor)
        v = await get_virtual_accounts(student_id=str(ObjectId()))
        assert len(v) == 1

    async def test_create_virtual_account(self, mock_db):
        from models.virtual_account import create_virtual_account
        oid = ObjectId()
        _mock_insert_one(mock_db, "virtual_accounts", oid)
        mock_db.students.find_one = AsyncMock(
            return_value={"_id": ObjectId(), "name": "Test", "nis": "001"})
        inv_oid = ObjectId()
        mock_db.invoices.find_one = AsyncMock(
            return_value={"_id": inv_oid, "total_amount": 150000, "paid_amount": 0})
        mock_db.va_invoice_lines.insert_many = AsyncMock()
        va = await create_virtual_account({
            "student_id": str(ObjectId()), "bank_code": "bca",
            "invoice_ids": [str(inv_oid)],
        })
        assert isinstance(va, dict)

    async def test_create_virtual_account_xendit_ok(self, mock_db):
        from models.virtual_account import create_virtual_account
        oid = ObjectId()
        inv_oid = ObjectId()
        _mock_insert_one(mock_db, "virtual_accounts", oid)
        mock_db.students.find_one = AsyncMock(
            return_value={"_id": ObjectId(), "name": "Siswa X", "nis": "002"})
        mock_db.invoices.find_one = AsyncMock(
            return_value={"_id": inv_oid, "total_amount": 50000, "paid_amount": 0})
        mock_db.va_invoice_lines.insert_many = AsyncMock()

        with patch("aiohttp.ClientSession") as mock_session_cls, \
             patch("models.virtual_account.Config") as mock_cfg:
            mock_cfg.XENDIT_API_KEY = "xnd_test_key"
            mock_cfg.XENDIT_API_URL = "https://api.xendit.co"
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"id": "va-x", "owner_id": "own"})
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=None),
            ))
            mock_session_cls.return_value = mock_session
            va = await create_virtual_account({
                "student_id": str(ObjectId()), "bank_code": "bni",
                "invoice_ids": [str(inv_oid)],
            })
            assert isinstance(va, dict)

    async def test_create_virtual_account_xendit_error(self, mock_db):
        from models.virtual_account import create_virtual_account
        inv_oid = ObjectId()
        mock_db.students.find_one = AsyncMock(
            return_value={"_id": ObjectId(), "name": "Siswa E", "nis": "003"})
        mock_db.invoices.find_one = AsyncMock(
            return_value={"_id": inv_oid, "total_amount": 50000, "paid_amount": 0})
        mock_db.va_invoice_lines.insert_many = AsyncMock()

        with patch("aiohttp.ClientSession") as mock_session_cls, \
             patch("models.virtual_account.Config") as mock_cfg:
            mock_cfg.XENDIT_API_KEY = "xnd_test_key"
            mock_cfg.XENDIT_API_URL = "https://api.xendit.co"
            mock_resp = MagicMock()
            mock_resp.status = 401
            mock_resp.json = AsyncMock(return_value={"error_code": "AUTH_ERROR"})
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=None),
            ))
            mock_session_cls.return_value = mock_session
            with pytest.raises(ValueError, match="Gagal"):
                await create_virtual_account({
                    "student_id": str(ObjectId()), "bank_code": "bni",
                    "invoice_ids": [str(inv_oid)],
                })

    async def test_mark_va_paid(self, mock_db):
        from models.virtual_account import mark_va_paid_manually
        oid = ObjectId()
        _mock_find_one(mock_db, "virtual_accounts", {
            "_id": oid, "status": "active", "student_id": ObjectId(),
            "amount": 150000, "bank_code": "bca",
        })
        _mock_find(mock_db, "va_invoice_lines", [{
            "invoice_id": ObjectId(), "amount": 50000,
        }])
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        mock_db.virtual_accounts.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        mock_db.payments.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId()))
        mock_db.payment_lines.insert_one = AsyncMock()
        result = await mark_va_paid_manually(str(oid))
        assert result is True

    async def test_cancel_va(self, mock_db):
        from models.virtual_account import cancel_va
        oid = ObjectId()
        result = await cancel_va(str(oid))
        assert result is True

    async def test_process_callback_paid(self, mock_db):
        from models.virtual_account import process_xendit_callback
        va_oid = ObjectId()
        mock_db.virtual_accounts.find_one_and_update = AsyncMock(
            return_value={
                "_id": va_oid, "student_id": ObjectId(),
                "amount": 50000, "external_id": "ext-123", "status": "pending",
            })
        mock_db.payments.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId()))
        mock_db.payment_lines.insert_one = AsyncMock()
        cursor = AsyncMock()
        cursor.to_list = AsyncMock(return_value=[{
            "invoice_id": ObjectId(), "amount": 50000,
        }])
        mock_db.va_invoice_lines.find = MagicMock(return_value=cursor)
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await process_xendit_callback({
            "external_id": "ext-123", "status": "PAID", "amount": 50000,
        })
        assert result is True

    async def test_process_callback_not_paid(self, mock_db):
        from models.virtual_account import process_xendit_callback
        result = await process_xendit_callback({
            "external_id": "ext-123", "status": "PENDING", "amount": 50000,
        })
        assert result is False

    async def test_process_callback_va_not_found(self, mock_db):
        from models.virtual_account import process_xendit_callback
        mock_db.virtual_accounts.find_one_and_update = AsyncMock(
            return_value=None)
        result = await process_xendit_callback({
            "external_id": "ext-123", "status": "PAID", "amount": 50000,
        })
        assert result is False

    async def test_process_callback_amount_mismatch(self, mock_db):
        from models.virtual_account import process_xendit_callback
        mock_db.virtual_accounts.find_one_and_update = AsyncMock(
            return_value={
                "_id": ObjectId(), "student_id": ObjectId(),
                "amount": 100000, "external_id": "ext-456",
                "status": "pending",
            })
        result = await process_xendit_callback({
            "external_id": "ext-456", "status": "PAID", "amount": 50000,
        })
        assert result is False


class TestPeriodModel:
    async def test_get_academic_years(self, mock_db):
        from models.period import get_academic_years
        _mock_find(mock_db, "academic_years", [{"name": "2025/2026"}])
        y = await get_academic_years()
        assert len(y) == 1

    async def test_get_active_academic_year(self, mock_db):
        from models.period import get_active_academic_year
        _mock_find_one(mock_db, "academic_years",
                       {"name": "2025/2026", "is_active": True})
        ay = await get_active_academic_year()
        assert ay["name"] == "2025/2026"

    async def test_get_active_academic_year_not_found(self, mock_db):
        from models.period import get_active_academic_year
        _mock_find_one(mock_db, "academic_years", None)
        ay = await get_active_academic_year()
        assert ay is None

    async def test_create_academic_year(self, mock_db):
        from models.period import create_academic_year
        oid = ObjectId()
        _mock_insert_one(mock_db, "academic_years", oid)
        result = await create_academic_year("2026/2027")
        assert result is not None

    async def test_toggle_academic_year(self, mock_db):
        from models.period import toggle_academic_year_active
        oid = ObjectId()
        mock_db.academic_years.update_many = AsyncMock()
        mock_db.academic_years.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await toggle_academic_year_active(str(oid))
        assert result is True

    async def test_delete_academic_year(self, mock_db):
        from models.period import delete_academic_year
        oid = ObjectId()
        result = await delete_academic_year(str(oid))
        assert result is True

    async def test_get_billing_periods(self, mock_db):
        from models.period import get_billing_periods
        _mock_find(mock_db, "billing_periods", [{"code": "202507"}])
        p = await get_billing_periods(str(ObjectId()))
        assert len(p) == 1

    async def test_create_billing_period(self, mock_db):
        from models.period import create_billing_period
        oid = ObjectId()
        _mock_insert_one(mock_db, "billing_periods", oid)
        pid = await create_billing_period({
            "name": "Juli 2025", "code": "202507",
            "start_date": "2025-07-01", "end_date": "2025-07-31",
            "academic_year_id": str(ObjectId()),
        })
        assert pid is not None

    async def test_update_billing_period(self, mock_db):
        from models.period import update_billing_period
        oid = ObjectId()
        mock_db.billing_periods.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_billing_period(str(oid), {
            "code": "202508", "name": "Agustus 2025",
            "start_date": "2025-08-01T00:00:00", "end_date": "2025-08-31T00:00:00",
            "academic_year_id": str(ObjectId()),
        })
        assert result is True

    async def test_delete_billing_period(self, mock_db):
        from models.period import delete_billing_period
        oid = ObjectId()
        result = await delete_billing_period(str(oid))
        assert result is True

    async def test_get_fee_configs(self, mock_db):
        from models.period import get_fee_configs
        _mock_find(mock_db, "fee_configs", [{"amount": 150000}])
        c = await get_fee_configs(str(ObjectId()))
        assert len(c) == 1

    async def test_upsert_fee_config(self, mock_db):
        from models.period import upsert_fee_config
        _mock_find_one(mock_db, "fee_configs", None)
        mock_db.fee_configs.update_one = AsyncMock(
            return_value=MagicMock(upserted_id=ObjectId(), modified_count=1))
        result = await upsert_fee_config({
            "academic_year_id": str(ObjectId()),
            "component_id": str(ObjectId()),
            "angkatan": 2025,
            "amount": 200000,
        })
        assert isinstance(result, dict)

    async def test_delete_fee_config(self, mock_db):
        from models.period import delete_fee_config
        oid = ObjectId()
        result = await delete_fee_config(str(oid))
        assert result is True


class TestBankAccountModel:
    async def test_get_bank_accounts(self, mock_db):
        from models.bank_account import get_bank_accounts
        _mock_find(mock_db, "bank_accounts", [{"bank_name": "BCA"}])
        b = await get_bank_accounts()
        assert len(b) == 1

    async def test_create_bank_account(self, mock_db):
        from models.bank_account import create_bank_account
        oid = ObjectId()
        _mock_insert_one(mock_db, "bank_accounts", oid)
        bid = await create_bank_account({
            "bank_name": "BCA", "account_no": "1234567890",
            "account_name": "Sekolah",
        })
        assert bid is not None

    async def test_update_bank_account(self, mock_db):
        from models.bank_account import update_bank_account
        oid = ObjectId()
        mock_db.bank_accounts.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1))
        result = await update_bank_account(str(oid), {
            "bank_name": "BNI", "account_no": "0987654321",
            "account_name": "Sekolah Baru",
        })
        assert result is True

    async def test_delete_bank_account(self, mock_db):
        from models.bank_account import delete_bank_account
        oid = ObjectId()
        result = await delete_bank_account(str(oid))
        assert result is True


class TestDashboardStats:
    async def test_dashboard_stats(self, mock_db):
        from models.dashboard import dashboard_stats
        _mock_count(mock_db, "students", 100)
        _mock_count(mock_db, "classes", 10)
        _mock_count(mock_db, "components", 5)
        _mock_count(mock_db, "invoices", 50)
        _mock_count(mock_db, "payments", 25)
        mock_db.payments.aggregate = MagicMock(return_value=AsyncMock(
            to_list=AsyncMock(return_value=[{"total": 500000}])))
        mock_db.invoices.aggregate = MagicMock(return_value=AsyncMock(
            to_list=AsyncMock(return_value=[{"_id": "x"}])))
        _mock_find(mock_db, "billing_periods", [])
        stats = await dashboard_stats()
        assert stats["total_students"] == 100
        assert stats["total_classes"] == 10


class TestAuditModel:
    async def test_log_audit(self, mock_db):
        from models.audit import log_audit
        mock_db.audit_logs.insert_one = AsyncMock()
        await log_audit("user@test.com", "create", "students",
                         "id123", {"old": "data"}, "test note")


class TestHelpers:
    def test_parse_bool_true(self):
        from models.helpers import parse_bool
        assert parse_bool(True) is True
        assert parse_bool(1) is True
        assert parse_bool("true") is True
        assert parse_bool("1") is True
        assert parse_bool("on") is True
        assert parse_bool("yes") is True

    def test_parse_bool_false(self):
        from models.helpers import parse_bool
        assert parse_bool(False) is False
        assert parse_bool(0) is False
        assert parse_bool("false") is False
        assert parse_bool("0") is False
        assert parse_bool("no") is False
        assert parse_bool("random") is False
        assert parse_bool(None) is False


class TestCloseDB:
    async def test_close_db(self, mock_db):
        import models.db
        models.db._client = MagicMock()
        await models.db.close_db()
        assert models.db._client is None

    async def test_collection(self, mock_db):
        from models.db import collection
        col = await collection("students")
        assert col is not None


class TestDBModule:
    async def test_get_next_sequence(self, mock_db):
        from models.db import get_next_sequence
        result = await get_next_sequence("payment")
        assert result == 1

    async def test_ensure_indexes(self, mock_db):
        from models.db import ensure_indexes
        await ensure_indexes()
        assert mock_db.students.create_index.called
        assert mock_db.user_profiles.create_index.called
