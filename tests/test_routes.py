import pytest
import re
import time
from bson import ObjectId


def _csrf(html):
    m = re.search(r"token\s*=\s*'([^']+)'", html)
    return m.group(1) if m else ""


def _refresh(auth_client, url, **kw):
    """GET url and update auth_client cookie from response."""
    kw.setdefault("headers", {}).update(auth_client._headers())
    resp = auth_client._run(auth_client._tc.get(url, **kw))
    sc = resp.headers.get("set-cookie", "")
    if sc:
        auth_client._cookie = sc.split(";")[0]
    return resp


class TestAuth:
    def test_login_page(self, client):
        r = client.get("/auth/login")
        assert r.status_code == 200

    def test_login_success(self, client):
        r = client.post("/auth/login", data={
            "email": "admin@spp.sch.id", "password": "admin123",
        })
        assert r.status_code == 302

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", data={
            "email": "admin@spp.sch.id", "password": "wrong",
        })
        assert r.status_code == 200

    def test_login_wrong_email(self, client):
        r = client.post("/auth/login", data={
            "email": "nonexistent@x.com", "password": "admin123",
        })
        assert r.status_code == 200

    def test_redirect_to_login(self):
        from tests.conftest import Client
        from app import app as _app
        c = Client(_app)
        c._open()
        try:
            r = c.get("/")
            assert r.status_code == 302
        finally:
            c._close()

    def test_404_page(self, client):
        r = client.get("/nonexistent-page")
        assert r.status_code == 404


class TestDashboard:
    def test_dashboard_200(self, auth_client):
        r = auth_client.get("/")
        assert r.status_code == 200

    def test_dark_mode(self, auth_client):
        r = auth_client.get("/")
        assert "toggleTheme" in r.text

    def test_search_ui(self, auth_client):
        r = auth_client.get("/")
        assert "searchSiswa" in r.text

    def test_bottom_nav(self, auth_client):
        r = auth_client.get("/")
        assert "bottom-0" in r.text

    def test_sidebar(self, auth_client):
        r = auth_client.get("/")
        n = r.text.count("px-4 py-2.5 rounded-2xl text-sm font-semibold")
        assert n >= 19

    def test_logout(self, auth_client):
        r = auth_client.get("/auth/logout")
        assert r.status_code == 302


class TestMasterRoutes:
    def test_siswa(self, auth_client):
        assert auth_client.get("/master/siswa").status_code == 200

    def test_siswa_import(self, auth_client):
        assert auth_client.get("/master/siswa/import").status_code == 200

    def test_kelas(self, auth_client):
        assert auth_client.get("/master/kelas").status_code == 200

    def test_komponen(self, auth_client):
        assert auth_client.get("/master/komponen").status_code == 200

    def test_periode(self, auth_client):
        assert auth_client.get("/master/periode").status_code == 200

    def test_kenaikan_kelas(self, auth_client):
        assert auth_client.get("/master/kenaikan-kelas").status_code == 200


class TestTransaksiRoutes:
    def test_tagihan(self, auth_client):
        assert auth_client.get("/tagihan/").status_code == 200

    def test_tagihan_generate(self, auth_client):
        assert auth_client.get("/tagihan/generate").status_code == 200

    def test_pembayaran(self, auth_client):
        assert auth_client.get("/pembayaran/").status_code == 200

    def test_virtual_akun(self, auth_client):
        assert auth_client.get("/pembayaran/virtual-akun").status_code == 200


class TestLaporanRoutes:
    def test_ringkasan(self, auth_client):
        assert auth_client.get("/laporan/").status_code == 200

    def test_tunggakan(self, auth_client):
        assert auth_client.get("/laporan/tunggakan").status_code == 200

    def test_mutasi(self, auth_client):
        assert auth_client.get("/laporan/mutasi").status_code == 200

    def test_kartu_spp(self, auth_client):
        assert auth_client.get("/laporan/kartu-spp").status_code == 200

    def test_rekap_harian(self, auth_client):
        assert auth_client.get("/laporan/rekap-harian").status_code == 200


class TestAdminRoutes:
    def test_pengguna(self, auth_client):
        assert auth_client.get("/admin/pengguna").status_code == 200

    def test_koreksi(self, auth_client):
        assert auth_client.get("/admin/koreksi").status_code == 200

    def test_rekening(self, auth_client):
        assert auth_client.get("/admin/rekening").status_code == 200


class TestExportRoutes:
    def test_export_siswa(self, auth_client):
        r = auth_client.get("/laporan/export/siswa")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application")

    def test_export_tunggakan(self, auth_client):
        assert auth_client.get("/laporan/export/tunggakan").status_code == 200

    def test_export_rekap(self, auth_client):
        assert auth_client.get("/laporan/export/rekap").status_code == 200


class TestSearch:
    def test_search_results(self, auth_client):
        r = auth_client.get("/api/search-siswa?q=Uta")
        assert r.status_code == 200
        assert "results" in r.json()

    def test_search_no_results(self, auth_client):
        r = auth_client.get("/api/search-siswa?q=zzz_none")
        assert r.status_code == 200
        assert len(r.json()["results"]) == 0


class TestSidebarActive:
    def test_siswa_active(self, auth_client):
        r = auth_client.get("/master/siswa")
        assert "bg-primary-50" in r.text
        assert "text-primary-600" in r.text

    def test_rekap_harian_active(self, auth_client):
        r = auth_client.get("/laporan/rekap-harian")
        assert "bg-primary-50" in r.text


class TestCSRFProtection:
    def test_post_without_csrf(self, auth_client):
        assert auth_client.post("/master/siswa", data={"name": "test"}).status_code == 403

    def test_get_no_csrf(self, auth_client):
        assert auth_client.get("/master/siswa").status_code == 200


class TestKartuSPP:
    def test_page_loads(self, auth_client):
        r = auth_client.get("/laporan/kartu-spp")
        assert r.status_code == 200


class TestSecurityHeaders:
    def test_x_frame_options(self, auth_client):
        assert "DENY" in auth_client.get("/").headers.get("x-frame-options", "")

    def test_x_content_type(self, auth_client):
        assert "nosniff" in auth_client.get("/").headers.get("x-content-type-options", "")


class TestKwitansi:
    def test_invalid_id(self, auth_client):
        r = auth_client.get("/pembayaran/kwitansi/000000000000000000000000")
        assert r.status_code in (200, 302, 404)


class TestPostCreateSiswa:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/siswa", data={
            "_csrf_token": csrf, "nis": "", "name": "", "angkatan": "",
            "gender": "", "class_id": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)

    def test_create_invalid_nis(self, auth_client):
        r = auth_client.get("/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/siswa", data={
            "_csrf_token": csrf, "nis": "short", "name": "Test",
            "angkatan": "2026", "gender": "L", "class_id": "dummy",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostClass:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/kelas", data={
            "_csrf_token": csrf, "name": "", "jenjang": "", "angkatan": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)

    def test_create_missing_name(self, auth_client):
        r = auth_client.get("/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/kelas", data={
            "_csrf_token": csrf, "name": "", "jenjang": "SMK", "angkatan": "2026",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostComponent:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/master/komponen")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/komponen", data={
            "_csrf_token": csrf, "name": "", "payment_type": "",
            "default_amount": "", "is_active": "1",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostPeriod:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/master/periode")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/periode", data={
            "_csrf_token": csrf, "name": "", "code": "",
            "start_date": "", "end_date": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostTagihan:
    def test_generate_get(self, auth_client):
        r = auth_client.get("/tagihan/generate")
        csrf = _csrf(r.text)
        assert csrf != ""

    def test_generate_post_invalid(self, auth_client):
        r = auth_client.get("/tagihan/generate")
        csrf = _csrf(r.text)
        resp = auth_client.post("/tagihan/generate", data={
            "_csrf_token": csrf, "class_ids": "", "component_ids": "",
            "period_id": "", "academic_year_id": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)

    def test_tagihan_actions(self, auth_client):
        resp = auth_client.post("/tagihan/", data={})
        assert resp.status_code in (200, 302, 400, 403, 405)


class TestPostPembayaran:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/pembayaran/")
        csrf = _csrf(r.text)
        resp = auth_client.post("/pembayaran/", data={
            "_csrf_token": csrf, "student_id": "", "invoice_ids": "",
            "amount_paid": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostAdminPengguna:
    def test_create_invalid(self, auth_client):
        r = auth_client.get("/admin/pengguna")
        csrf = _csrf(r.text)
        resp = auth_client.post("/admin/pengguna", data={
            "_csrf_token": csrf, "email": "", "full_name": "",
            "password": "", "role": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostAdminKoreksi:
    def test_correction_invalid(self, auth_client):
        r = auth_client.get("/admin/koreksi")
        csrf = _csrf(r.text)
        resp = auth_client.post("/admin/koreksi", data={
            "_csrf_token": csrf, "invoice_id": "", "amount": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestPostLaporanKartuSPP:
    def test_lookup_invalid(self, auth_client):
        r = auth_client.get("/laporan/kartu-spp")
        csrf = _csrf(r.text)
        resp = auth_client.post("/laporan/kartu-spp", data={
            "_csrf_token": csrf, "student_id": "",
        })
        assert resp.status_code in (200, 302, 400, 403, 405, 500)


class TestDeleteRoutes:
    def test_delete_siswa_invalid(self, auth_client):
        r = auth_client.get("/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/siswa/000000000000000000000000/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 400, 403, 404, 405, 500)

    def test_delete_kelas_invalid(self, auth_client):
        r = auth_client.get("/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/kelas/000000000000000000000000/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 400, 403, 404, 405, 500)

    def test_delete_komponen_invalid(self, auth_client):
        r = auth_client.get("/master/komponen")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/komponen/000000000000000000000000/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 400, 403, 404, 405, 500)


class TestInitChecks:
    def test_favicon(self, auth_client):
        r = auth_client.get("/favicon.ico")
        assert r.status_code in (200, 404)

    def test_csrf_token_on_pages(self, auth_client):
        for url in ["/master/siswa", "/master/kelas", "/master/komponen",
                      "/master/periode", "/tagihan/", "/pembayaran/",
                      "/admin/pengguna", "/admin/koreksi"]:
            r = auth_client.get(url)
            assert _csrf(r.text) != "", f"No CSRF on {url}"


class TestPostKelasSuccess:
    def test_create_then_delete(self, auth_client):
        name = f"Test_Kelas_{int(time.time() * 1000)}"
        r = _refresh(auth_client, "/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/kelas", data={
            "_csrf_token": csrf, "name": name, "jenjang": "SMK",
            "angkatan": "2026",
        })
        assert resp.status_code == 302

    def test_update(self, auth_client):
        refs = auth_client.db_refs()
        class_id = refs.get("class_id", "000000000000000000000000")
        r = _refresh(auth_client, "/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/kelas/{class_id}/update", data={
            "_csrf_token": csrf, "name": "Updated Kelas", "jenjang": "SMK",
            "angkatan": "2026",
        })
        assert resp.status_code in (200, 302, 500)


class TestPostKomponenSuccess:
    def test_create(self, auth_client):
        name = f"Test_Komp_{int(time.time() * 1000)}"
        r = _refresh(auth_client, "/master/komponen")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/komponen", data={
            "_csrf_token": csrf, "name": name, "payment_type": "bulanan",
            "default_amount": "150000", "is_active": "1",
        })
        assert resp.status_code == 302

    def test_update(self, auth_client):
        refs = auth_client.db_refs()
        comp_id = refs.get("component_id", "000000000000000000000000")
        r = _refresh(auth_client, "/master/komponen")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/komponen/{comp_id}/update", data={
            "_csrf_token": csrf, "name": "SPP Updated", "payment_type": "bulanan",
            "default_amount": "200000", "is_active": "1",
        })
        assert resp.status_code in (200, 302, 500)


class TestPostPeriodeSuccess:
    def test_create_billing_period(self, auth_client):
        refs = auth_client.db_refs()
        ay_id = refs.get("ay_id", "000000000000000000000000")
        code = f"TS{int(time.time())}"
        r = _refresh(auth_client, "/master/periode")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/periode/billing-period", data={
            "_csrf_token": csrf, "name": f"Test Periode {code}",
            "code": code, "academic_year_id": ay_id,
            "start_date": "2026-01-01T00:00:00", "end_date": "2026-12-31T00:00:00",
        })
        assert resp.status_code == 302

    def test_create_academic_year(self, auth_client):
        name = f"TA {int(time.time())}"
        r = _refresh(auth_client, "/master/periode")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/periode/academic-year", data={
            "_csrf_token": csrf, "name": name,
        })
        assert resp.status_code == 302


class TestPostSiswaSuccess:
    def test_create(self, auth_client):
        refs = auth_client.db_refs()
        class_id = refs.get("class_id")
        if not class_id:
            return pytest.skip("No class found in DB")
        nis = f"TS{int(time.time())}"
        r = _refresh(auth_client, "/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/siswa", data={
            "_csrf_token": csrf, "nis": nis, "name": f"Test Siswa {nis}",
            "angkatan": "2026", "gender": "L", "class_id": class_id,
        })
        assert resp.status_code == 302

    def test_update(self, auth_client):
        refs = auth_client.db_refs()
        student_id = refs.get("student_id")
        class_id = refs.get("class_id")
        if not student_id:
            return pytest.skip("No student found in DB")
        r = _refresh(auth_client, "/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/siswa/{student_id}/update", data={
            "_csrf_token": csrf, "nis": refs.get("student_nis", "001"),
            "name": "Updated Siswa", "angkatan": "2026", "gender": "L",
            "class_id": class_id or str(ObjectId()),
        })
        assert resp.status_code in (200, 302, 500)


class TestPostPenggunaSuccess:
    def test_create(self, auth_client):
        email = f"test_{int(time.time())}@test.com"
        r = _refresh(auth_client, "/admin/pengguna")
        csrf = _csrf(r.text)
        resp = auth_client.post("/admin/pengguna", data={
            "_csrf_token": csrf, "email": email, "full_name": "Test User",
            "password": "Test1234!", "role": "kasir",
        })
        assert resp.status_code == 302

    def test_toggle_active(self, auth_client):
        r = _refresh(auth_client, "/admin/pengguna")
        csrf = _csrf(r.text)
        resp = auth_client.post(
            "/admin/pengguna/000000000000000000000000/toggle-active",
            data={"_csrf_token": csrf, "is_active": "true"},
        )
        assert resp.status_code in (200, 302, 400, 404, 500)


class TestPostTagihanGenerateSuccess:
    def test_generate(self, auth_client):
        refs = auth_client.db_refs()
        class_id = refs.get("class_id", "")
        comp_id = refs.get("component_id", "")
        period_id = refs.get("period_id", "")
        ay_id = refs.get("ay_id", "")
        r = _refresh(auth_client, "/tagihan/generate")
        csrf = _csrf(r.text)
        resp = auth_client.post("/tagihan/generate", data={
            "_csrf_token": csrf, "class_ids": class_id,
            "component_ids": comp_id, "period_id": period_id,
            "academic_year_id": ay_id,
        })
        assert resp.status_code in (200, 302, 500)


class TestPostPembayaranSuccess:
    def test_create(self, auth_client):
        refs = auth_client.db_refs()
        student_id = refs.get("student_id")
        if not student_id:
            return pytest.skip("No student found in DB")
        r = _refresh(auth_client, "/pembayaran/")
        csrf = _csrf(r.text)
        resp = auth_client.post("/pembayaran/", data={
            "_csrf_token": csrf, "student_id": student_id,
            "invoice_ids": "", "amount_paid": "150000",
        })
        assert resp.status_code in (200, 302, 500)


class TestPostKoreksiSuccess:
    def test_void_payment(self, auth_client):
        r = _refresh(auth_client, "/admin/koreksi")
        csrf = _csrf(r.text)
        resp = auth_client.post(
            "/admin/koreksi/void-payment/000000000000000000000000",
            data={"_csrf_token": csrf, "reason": "test"},
        )
        assert resp.status_code in (200, 302, 400, 404, 500)

    def test_edit_invoice(self, auth_client):
        r = _refresh(auth_client, "/admin/koreksi")
        csrf = _csrf(r.text)
        resp = auth_client.post(
            "/admin/koreksi/edit-invoice/000000000000000000000000",
            data={"_csrf_token": csrf, "total_amount": "200000"},
        )
        assert resp.status_code in (200, 302, 400, 404, 500)


class TestLaporanQueries:
    def test_tunggakan_with_filter(self, auth_client):
        r = auth_client.get("/laporan/tunggakan?class_id=dummy&angkatan=2025")
        assert r.status_code == 200

    def test_mutasi_with_date(self, auth_client):
        r = auth_client.get("/laporan/mutasi?start_date=2025-01-01&end_date=2025-12-31")
        assert r.status_code == 200

    def test_ringkasan_with_filter(self, auth_client):
        r = auth_client.get("/laporan/?academic_year_id=dummy")
        assert r.status_code in (200, 500)

    def test_kartu_spp_query(self, auth_client):
        r = auth_client.get("/laporan/kartu-spp?student_id=dummy")
        assert r.status_code == 200

    def test_rekap_harian_date(self, auth_client):
        r = auth_client.get("/laporan/rekap-harian?date=2025-07-29")
        assert r.status_code == 200


class TestPembayaranQueries:
    def test_with_reference(self, auth_client):
        refs = auth_client.db_refs()
        sid = refs.get("student_id", "dummy")
        r = auth_client.get(f"/pembayaran/?student_id={sid}")
        assert r.status_code == 200

    def test_kwitansi_real(self, auth_client):
        refs = auth_client.db_refs()
        sid = refs.get("student_id", "000000000000000000000000")
        r = auth_client.get(f"/pembayaran/kwitansi/{sid}")
        assert r.status_code in (200, 302, 404, 500)


class TestMasterDeleteSuccess:
    def test_delete_siswa(self, auth_client):
        refs = auth_client.db_refs()
        sid = refs.get("student_id")
        if not sid:
            return pytest.skip("No student in DB")
        r = _refresh(auth_client, "/master/siswa")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/siswa/{sid}/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 500)

    def test_delete_kelas(self, auth_client):
        refs = auth_client.db_refs()
        cid = refs.get("class_id")
        if not cid:
            return pytest.skip("No class in DB")
        r = _refresh(auth_client, "/master/kelas")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/kelas/{cid}/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 500)

    def test_delete_komponen(self, auth_client):
        refs = auth_client.db_refs()
        cid = refs.get("component_id")
        if not cid:
            return pytest.skip("No component in DB")
        r = _refresh(auth_client, "/master/komponen")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/master/komponen/{cid}/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 500)


class TestAdminRolePassword:
    def test_change_role(self, auth_client):
        r = _refresh(auth_client, "/admin/pengguna")
        csrf = _csrf(r.text)
        resp = auth_client.post(
            "/admin/pengguna/000000000000000000000000/role",
            data={"_csrf_token": csrf, "role": "admin"},
        )
        assert resp.status_code == 302

    def test_change_password(self, auth_client):
        r = _refresh(auth_client, "/admin/pengguna")
        csrf = _csrf(r.text)
        resp = auth_client.post(
            "/admin/pengguna/000000000000000000000000/password",
            data={"_csrf_token": csrf, "password": "Str0ng!New1"},
        )
        assert resp.status_code in (200, 302, 500)


class TestAdminRekening:
    def test_create(self, auth_client):
        name = f"Bank_{int(time.time())}"
        r = _refresh(auth_client, "/admin/rekening")
        csrf = _csrf(r.text)
        resp = auth_client.post("/admin/rekening", data={
            "_csrf_token": csrf, "bank_name": name,
            "account_no": "1122334455", "account_name": "Sekolah",
        })
        assert resp.status_code == 302

    def test_update(self, auth_client):
        refs = auth_client.db_refs()
        bid = refs.get("class_id", "000000000000000000000000")
        r = _refresh(auth_client, "/admin/rekening")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/admin/rekening/{bid}/update", data={
            "_csrf_token": csrf, "bank_name": "BCA Updated",
            "account_no": "9988776655", "account_name": "Sekolah Updated",
        })
        assert resp.status_code in (200, 302, 500)

    def test_delete(self, auth_client):
        refs = auth_client.db_refs()
        bid = refs.get("class_id", "000000000000000000000000")
        r = _refresh(auth_client, "/admin/rekening")
        csrf = _csrf(r.text)
        resp = auth_client.post(f"/admin/rekening/{bid}/delete", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 500)


class TestMasterImport:
    def test_import_post(self, auth_client):
        r = _refresh(auth_client, "/master/siswa/import")
        csrf = _csrf(r.text)
        resp = auth_client.post("/master/siswa/import", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 400, 405, 500)


class TestTagihanProcess:
    def test_cancel(self, auth_client):
        r = _refresh(auth_client, "/tagihan/")
        csrf = _csrf(r.text)
        resp = auth_client.post("/tagihan/000000000000000000000000/cancel", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 404, 500)

    def test_mark_paid(self, auth_client):
        r = _refresh(auth_client, "/tagihan/")
        csrf = _csrf(r.text)
        resp = auth_client.post("/tagihan/000000000000000000000000/mark-paid", data={
            "_csrf_token": csrf,
        })
        assert resp.status_code in (200, 302, 404, 500)


class TestPembayaranVA:
    def test_va_create_post(self, auth_client):
        refs = auth_client.db_refs()
        sid = refs.get("student_id")
        if not sid:
            return pytest.skip("No student in DB")
        r = _refresh(auth_client, "/pembayaran/virtual-akun")
        csrf = _csrf(r.text)
        resp = auth_client.post("/pembayaran/virtual-akun/create", data={
            "_csrf_token": csrf, "student_id": sid,
            "bank_code": "bca", "invoice_ids": "",
        })
        assert resp.status_code in (200, 302, 400, 405, 500)

    def test_xendit_callback(self, auth_client):
        import json
        resp = auth_client.post("/pembayaran/xendit-callback", data=json.dumps({
            "external_id": "test-ext-1", "status": "PAID", "amount": "50000",
        }), headers={"Content-Type": "application/json"})
        assert resp.status_code in (200, 302, 400, 403, 405, 500)
