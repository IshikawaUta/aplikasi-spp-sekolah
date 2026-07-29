from bson import ObjectId
from fenrir import Blueprint, g, redirect, render_template, request

from models.audit import log_audit
from models.bank_account import (
    create_bank_account,
    delete_bank_account,
    get_bank_accounts,
    update_bank_account,
)
from models.invoice import get_invoices, update_invoice
from models.payment import get_payments, void_payment
from models.user import (
    create_user,
    get_users,
    toggle_user_active,
    update_user_password,
    update_user_role,
)
from routes.decorators import admin_required, csrf_protect, validate_object_id

bp = Blueprint("admin", url_prefix="/admin")


@bp.get("/pengguna")
@admin_required
async def pengguna_list():
    users = await get_users()
    return render_template("admin/pengguna.html.j2", users=users, active_page="pengguna")


@bp.post("/pengguna")
@csrf_protect
@admin_required
async def pengguna_create():
    data = await request.form()
    try:
        await create_user(data["email"], data["full_name"], data["password"], data.get("role", "kasir"))
        await log_audit(g.user["email"], "create", "user_profiles", None, None,
                        f"Created user {data['email']} with role {data.get('role', 'kasir')}")
    except Exception as e:  # noqa: BLE001
        return render_template("admin/pengguna.html.j2",
                               users=await get_users(),
                               error=str(e),
                               active_page="pengguna")
    return redirect("/admin/pengguna")


@bp.post("/pengguna/<id>/role")
@csrf_protect
@validate_object_id("id")
@admin_required
async def pengguna_role(id: str):
    data = await request.form()
    new_role = data.get("role", "").strip()
    if not new_role:
        return redirect("/admin/pengguna?error=Role+tidak+boleh+kosong")
    await update_user_role(id, new_role)
    await log_audit(g.user["email"], "update_role", "user_profiles", id, None,
                    f"Changed role to {new_role}")
    return redirect("/admin/pengguna")


@bp.post("/pengguna/<id>/password")
@csrf_protect
@validate_object_id("id")
@admin_required
async def pengguna_password(id: str):
    data = await request.form()
    password = data.get("password", "").strip()
    if not password:
        return redirect("/admin/pengguna?error=Password+tidak+boleh+kosong")
    await update_user_password(id, password)
    await log_audit(g.user["email"], "change_password", "user_profiles", id, None, "Password changed")
    return redirect("/admin/pengguna")


@bp.post("/pengguna/<id>/toggle-active")
@csrf_protect
@validate_object_id("id")
@admin_required
async def pengguna_toggle(id: str):
    data = await request.form()
    is_active = data.get("is_active", "true") == "true"
    await toggle_user_active(id, is_active)
    return redirect("/admin/pengguna")


@bp.get("/koreksi")
@admin_required
async def koreksi_page():
    payments = await get_payments()
    invoices = await get_invoices()
    db = g.db
    audit_logs = await db.audit_logs.find().sort("created_at", -1).limit(100).to_list(None)
    return render_template("admin/koreksi.html.j2",
                           payments=payments, invoices=invoices,
                           audit_logs=audit_logs,
                           active_page="koreksi")


@bp.post("/koreksi/void-payment/<payment_id>")
@csrf_protect
@validate_object_id("payment_id")
@admin_required
async def koreksi_void(payment_id: str):
    data = await request.form()
    reason = data.get("reason", "")
    await void_payment(payment_id, reason, g.user["email"])
    await log_audit(g.user["email"], "void_payment", "payments", payment_id, None,
                    f"Voided payment: {reason}")
    return redirect("/admin/koreksi")


@bp.post("/koreksi/edit-invoice/<invoice_id>")
@csrf_protect
@validate_object_id("invoice_id")
@admin_required
async def koreksi_edit_invoice(invoice_id: str):
    data = await request.form()
    old_invoice = await g.db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not old_invoice:
        return redirect("/admin/koreksi?error=Tagihan+tidak+ditemukan")
    await update_invoice(invoice_id, data)
    await log_audit(g.user["email"], "edit_invoice", "invoices", invoice_id,
                    {"amount": old_invoice["total_amount"], "status": old_invoice["status"]},
                    f"Corrected invoice: {data.get('notes', '')}")
    return redirect("/admin/koreksi")


@bp.get("/rekening")
@admin_required
async def rekening_list():
    bank_accounts = await get_bank_accounts()
    return render_template("admin/rekening.html.j2", bank_accounts=bank_accounts, active_page="rekening")


@bp.post("/rekening")
@csrf_protect
@admin_required
async def rekening_create():
    data = await request.form()
    await create_bank_account(data)
    return redirect("/admin/rekening")


@bp.post("/rekening/<id>/update")
@csrf_protect
@validate_object_id("id")
@admin_required
async def rekening_update(id: str):
    data = await request.form()
    await update_bank_account(id, data)
    return redirect("/admin/rekening")


@bp.post("/rekening/<id>/delete")
@csrf_protect
@validate_object_id("id")
@admin_required
async def rekening_delete(id: str):
    await delete_bank_account(id)
    return redirect("/admin/rekening")
