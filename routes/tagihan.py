from bson import ObjectId
from fenrir import Blueprint, g, redirect, render_template, request

from models.audit import log_audit
from models.class_model import get_classes
from models.component import get_components
from models.invoice import (
    cancel_invoice,
    create_invoice,
    get_invoices,
    mass_generate_invoices,
    update_invoice,
    update_invoice_paid_off,
)
from models.period import get_academic_years, get_billing_periods
from models.student import get_students
from routes.decorators import (
    admin_required,
    csrf_protect,
    login_required,
    validate_object_id,
)

bp = Blueprint("tagihan", url_prefix="/tagihan")


@bp.get("/")
@login_required
async def tagihan_list():
    class_id = request.args.get("class_id", "")
    status = request.args.get("status", "")
    filt = {}
    if status:
        filt["status"] = status
    if class_id:
        students = await get_students(class_id)
        filt["student_id"] = {"$in": [ObjectId(s["_id"]) for s in students]}

    invoices = await get_invoices(filt)
    students = await get_students()
    classes = await get_classes()
    components = await get_components(active_only=True)
    periods = []
    active_ay = None
    academic_years = await get_academic_years()
    for ay in academic_years:
        if ay.get("is_active"):
            active_ay = ay
            break
    if active_ay:
        periods = await get_billing_periods(str(active_ay["_id"]))

    return render_template("tagihan/index.html.j2",
                           invoices=invoices, students=students, classes=classes,
                           components=components, periods=periods,
                           academic_years=academic_years, active_ay=active_ay,
                           active_page="tagihan")


@bp.post("/")
@csrf_protect
@admin_required
@login_required
async def tagihan_create():
    data = await request.form()
    await create_invoice(data)
    return redirect("/tagihan/")


@bp.post("/<id>/update")
@csrf_protect
@validate_object_id("id")
@admin_required
@login_required
async def tagihan_update(id: str):
    data = await request.form()
    await update_invoice(id, data)
    return redirect("/tagihan/")


@bp.post("/<id>/cancel")
@csrf_protect
@validate_object_id("id")
@admin_required
@login_required
async def tagihan_cancel(id: str):
    await cancel_invoice(id)
    return redirect("/tagihan/")


@bp.post("/<id>/paid-off")
@csrf_protect
@validate_object_id("id")
@admin_required
@login_required
async def tagihan_paid_off(id: str):
    data = await request.form()
    paid_off_at = data.get("paid_off_at", "").strip()
    if not paid_off_at:
        return redirect("/tagihan/")
    await update_invoice_paid_off(id, paid_off_at)
    return redirect("/tagihan/")


@bp.get("/generate")
@login_required
async def tagihan_generate_form():
    academic_years = await get_academic_years()
    classes = await get_classes()
    components = await get_components(active_only=True)
    periods = []
    active_ay = None
    for ay in academic_years:
        if ay.get("is_active"):
            active_ay = ay
            break
    if active_ay:
        periods = await get_billing_periods(str(active_ay["_id"]))
    return render_template("tagihan/generate.html.j2",
                           academic_years=academic_years, classes=classes,
                           components=components, periods=periods,
                           active_ay=active_ay, active_page="tagihan_generate",
                           preview=None)


@bp.post("/generate")
@csrf_protect
@admin_required
@login_required
async def tagihan_generate_action():
    data = await request.form()
    action = data.get("action", "preview")

    class_ids = data.get("class_ids", [])
    if isinstance(class_ids, str):
        class_ids = [class_ids]
    component_ids = data.get("component_ids", [])
    if isinstance(component_ids, str):
        component_ids = [component_ids]
    period_id = data.get("period_id", "")
    academic_year_id = data.get("academic_year_id", "")

    if action == "generate":
        result = await mass_generate_invoices(class_ids, component_ids, period_id, academic_year_id)
        await log_audit(g.user["email"], "mass_generate", "invoices", None, None,
                        f"Generated {result['new_count']} invoices for period {period_id}")
        return redirect(f"/tagihan/generate?generated={result['new_count']}&skipped={result['skip_count']}")

    # Preview
    result = await mass_generate_invoices(class_ids, component_ids, period_id, academic_year_id)
    academic_years = await get_academic_years()
    classes = await get_classes()
    components = await get_components(active_only=True)
    periods = []
    active_ay = None
    for ay in academic_years:
        if ay.get("is_active"):
            active_ay = ay
            break
    if active_ay:
        periods = await get_billing_periods(str(active_ay["_id"]))

    return render_template("tagihan/generate.html.j2",
                           academic_years=academic_years, classes=classes,
                           components=components, periods=periods,
                           active_ay=active_ay, active_page="tagihan_generate",
                           preview=result)


@bp.post("/generate-bulk")
@admin_required
@login_required
@csrf_protect
async def generate_bulk_action():
    data = await request.form()
    academic_year_id = data.get("academic_year_id", "")
    period_id = data.get("period_id", "")

    class_ids = data.get("class_ids", [])
    if isinstance(class_ids, str):
        class_ids = [class_ids]
    component_ids = data.get("component_ids", [])
    if isinstance(component_ids, str):
        component_ids = [component_ids]

    if not academic_year_id or not period_id or not component_ids or not class_ids:
        academic_years = await get_academic_years()
        if not academic_years:
            periods = []
        else:
            periods = await get_billing_periods(str(academic_years[0]["_id"]))
        components = await get_components(active_only=True)
        classes = await get_classes()
        return render_template("tagihan/generate.html.j2",
            academic_years=academic_years, periods=periods,
            components=components, classes=classes,
            active_page="tagihan_generate", preview=None,
            error="Pilih minimal satu kelas dan satu komponen")

    total_new = 0
    total_skip = 0

    for class_id in class_ids:
        result = await mass_generate_invoices([class_id], component_ids, period_id, academic_year_id)
        total_new += result["new_count"]
        total_skip += result["skip_count"]

    return redirect(f"/tagihan/generate?generated={total_new}&skipped={total_skip}")
