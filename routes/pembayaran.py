from bson import ObjectId
from fenrir import Blueprint, g, redirect, render_template, request

from models.audit import log_audit
from models.bank_account import get_bank_accounts
from models.class_model import get_classes
from models.invoice import get_invoices
from models.payment import (
    create_payment,
    get_payment_by_id,
    get_payment_lines,
    get_payments,
)
from models.student import get_students
from models.virtual_account import (
    BANK_CODES,
    cancel_va,
    create_virtual_account,
    get_virtual_accounts,
    mark_va_paid_manually,
)
from routes.decorators import (
    admin_required,
    csrf_protect,
    login_required,
    validate_object_id,
)

bp = Blueprint("pembayaran", url_prefix="/pembayaran")


@bp.get("/")
@login_required
async def pembayaran_form():
    class_id = request.args.get("class_id", "")
    student_id = request.args.get("student_id", "")
    classes = await get_classes()
    students = await get_students(class_id if class_id else None)
    unpaid_invoices = []
    payments = await get_payments({"is_voided": {"$ne": True}})
    bank_accounts = await get_bank_accounts(active_only=True)

    if student_id:
        filt = {"student_id": ObjectId(student_id), "status": {"$in": ["draft", "posted"]}}
        unpaid_invoices = await get_invoices(filt)

    return render_template("pembayaran/index.html.j2",
                           classes=classes, students=students,
                           unpaid_invoices=unpaid_invoices, payments=payments,
                           bank_accounts=bank_accounts,
                           selected_student_id=student_id,
                           active_page="pembayaran")


@bp.post("/")
@csrf_protect
@admin_required
@login_required
async def pembayaran_process():
    data = await request.form()
    student_id = data.get("student_id", "")
    payment_date = data.get("payment_date", "")

    lines = []
    for key in data:
        if key.startswith("pay_"):
            invoice_id = key.replace("pay_", "")
            amount = int(data.get(key, 0) or 0)
            if amount > 0:
                lines.append({"invoice_id": invoice_id, "amount_paid": amount})

    if not lines:
        return redirect(f"/pembayaran/?student_id={student_id}")

    payment_data = {
        "student_id": student_id,
        "payment_date": payment_date,
    }
    payment_id = await create_payment(payment_data, lines)
    await log_audit(g.user["email"], "create", "payments", payment_id, None,
                    f"Payment for student {student_id}")
    return redirect(f"/pembayaran/?student_id={student_id}")


@bp.get("/virtual-akun")
@login_required
async def va_page():
    student_id = request.args.get("student_id", "")
    students = await get_students()
    vas = await get_virtual_accounts(student_id if student_id else None)

    unpaid_invoices = []
    if student_id:
        filt = {"student_id": ObjectId(student_id), "status": {"$in": ["draft", "posted"]}}
        unpaid_invoices = await get_invoices(filt)

    return render_template("pembayaran/virtual-akun.html.j2",
                           students=students,
                           vas=vas,
                           bank_codes=BANK_CODES,
                           unpaid_invoices=unpaid_invoices,
                           selected_student_id=student_id,
                           active_page="va")


@bp.post("/virtual-akun/create")
@csrf_protect
@admin_required
@login_required
async def va_create():
    data = await request.form()
    try:
        va = await create_virtual_account(data)
        await log_audit(g.user["email"], "create", "virtual_accounts",
                        str(va["_id"]), None,
                        f"VA {va.get('bank_code','')} for student {data.get('student_id','')}")
        return render_template("pembayaran/va_result.html.j2",
                               va=va, bank_codes=BANK_CODES, active_page="va")
    except ValueError as e:
        return {"error": str(e)}, 400


@bp.post("/virtual-akun/<va_id>/mark-paid")
@csrf_protect
@validate_object_id("va_id")
@admin_required
@login_required
async def va_mark_paid(va_id: str):
    await mark_va_paid_manually(va_id)
    await log_audit(g.user["email"], "mark_paid", "virtual_accounts", va_id, None,
                    "Manually marked as paid")
    return redirect("/pembayaran/virtual-akun")


@bp.post("/virtual-akun/<va_id>/cancel")
@csrf_protect
@validate_object_id("va_id")
@admin_required
@login_required
async def va_cancel(va_id: str):
    await cancel_va(va_id)
    await log_audit(g.user["email"], "cancel", "virtual_accounts", va_id, None,
                    "VA cancelled")
    return redirect("/pembayaran/virtual-akun")


@bp.get("/kwitansi/<payment_id>")
@login_required
@validate_object_id("payment_id")
async def kwitansi(payment_id: str):
    db = g.db
    payment = await get_payment_by_id(payment_id)
    if not payment:
        return "Pembayaran tidak ditemukan", 404

    student = await db.students.find_one({"_id": payment.get("student_id")})
    lines = await get_payment_lines(payment_id)

    invoice_details = []
    total_bayar = 0
    for line in lines:
        inv = await db.invoices.find_one({"_id": line["invoice_id"]})
        if inv:
            component = await db.components.find_one({"_id": inv.get("component_id")})
            invoice_details.append({
                "component": component["name"] if component else "-",
                "amount_paid": line["amount_paid"],
            })
            total_bayar += line["amount_paid"]

    return render_template("pembayaran/kwitansi.html.j2",
        payment=payment, student=student,
        invoice_details=invoice_details, total_bayar=total_bayar)


@bp.post("/xendit-callback")
async def xendit_callback():
    from config import Config
    from models.virtual_account import process_xendit_callback
    payload = request.json or {}
    token = request.headers.get("x-callback-token", "")
    if Config.XENDIT_CALLBACK_TOKEN and token != Config.XENDIT_CALLBACK_TOKEN:
        return {"error": "Invalid callback token"}, 403
    try:
        ok = await process_xendit_callback(payload)
        return {"status": "ok" if ok else "ignored"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}, 400
