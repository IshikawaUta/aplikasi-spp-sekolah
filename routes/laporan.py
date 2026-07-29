from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from bson import ObjectId
from fenrir import Blueprint, Response, g, render_template, request

from config import Config
from models.class_model import get_classes
from models.component import get_components
from models.invoice import get_invoices
from models.payment import get_payments
from models.period import get_academic_years, get_billing_periods
from models.student import get_student_by_id, get_students
from routes.decorators import login_required
from services.exporter import auto_width, create_workbook, set_header_style, to_bytes


def safe_object_id(val: str):
    from bson import ObjectId, errors
    try:
        return ObjectId(val)
    except (errors.InvalidId, TypeError):
        return None


bp = Blueprint("laporan", url_prefix="/laporan")


@bp.get("/")
@login_required
async def laporan_index():
    academic_years = await get_academic_years()
    classes = await get_classes()

    ay_id = request.args.get("academic_year_id", "")
    period_id = request.args.get("period_id", "")
    status = request.args.get("status", "")

    filt = {}
    if period_id:
        oid = safe_object_id(period_id)
        if oid:
            filt["period_id"] = oid
    if status:
        filt["status"] = status

    invoices = await get_invoices(filt)
    payments = await get_payments({"is_voided": {"$ne": True}})

    total_inv = len(invoices)
    total_paid = sum(1 for inv in invoices if inv.get("status") == "paid")
    total_outstanding = total_inv - total_paid
    total_amount = sum(inv.get("total_amount", 0) for inv in invoices)
    total_paid_amount = sum(inv.get("paid_amount", 0) for inv in invoices)
    collection_rate = (total_paid_amount / total_amount * 100) if total_amount > 0 else 0

    periods = []
    if ay_id:
        periods = await get_billing_periods(ay_id)

    return render_template("laporan/index.html.j2",
                           academic_years=academic_years, classes=classes,
                           invoices=invoices, payments=payments,
                           total_inv=total_inv, total_paid=total_paid,
                           total_outstanding=total_outstanding,
                           total_amount=total_amount,
                           total_paid_amount=total_paid_amount,
                           collection_rate=collection_rate,
                           periods=periods,
        active_page="laporan")


@bp.get("/tunggakan")
@login_required
async def tunggakan_report():
    db = g.db
    academic_years = await get_academic_years()
    classes = await get_classes()
    components = await get_components()

    ay_id = request.args.get("academic_year_id", "")
    class_id = request.args.get("class_id", "")
    angkatan = request.args.get("angkatan", "")
    component_id = request.args.get("component_id", "")

    filt = {"status": {"$in": ["draft", "posted"]}}
    if ay_id:
        oid = safe_object_id(ay_id)
        if oid:
            periods = await db.billing_periods.find({"academic_year_id": oid}).to_list(None)
            period_ids = [p["_id"] for p in periods]
            if period_ids:
                filt["period_id"] = {"$in": period_ids}
    if class_id:
        oid = safe_object_id(class_id)
        if oid:
            students_in_class = await db.students.find({"class_id": oid}).to_list(None)
            student_ids = [s["_id"] for s in students_in_class]
            filt["student_id"] = {"$in": student_ids}
    if angkatan:
        try:
            angkatan_int = int(angkatan)
        except (ValueError, TypeError):
            angkatan_int = 0
        students_angkatan = await db.students.find({"angkatan": angkatan_int}).to_list(None)
        student_ids_a = [s["_id"] for s in students_angkatan]
        if "student_id" in filt:
            filt["student_id"]["$in"] = [x for x in filt["student_id"]["$in"] if x in student_ids_a]
        else:
            filt["student_id"] = {"$in": student_ids_a}
    if component_id:
        oid = safe_object_id(component_id)
        if oid:
            filt["component_id"] = oid

    invoices = await get_invoices(filt)

    report_data = {}
    for inv in invoices:
        sid = str(inv.get("student_id", ""))
        if sid not in report_data:
            report_data[sid] = {"student": inv.get("student"), "total": 0, "outstanding": 0, "details": []}
        remaining = inv.get("total_amount", 0) - inv.get("paid_amount", 0)
        report_data[sid]["total"] += inv.get("total_amount", 0)
        report_data[sid]["outstanding"] += remaining
        report_data[sid]["details"].append(inv)

    sorted_data = sorted(report_data.values(), key=lambda x: x["outstanding"], reverse=True)

    total_outstanding = sum(d["outstanding"] for d in sorted_data)
    student_count = len(sorted_data)

    return render_template("laporan/tunggakan.html.j2",
                           report_data=sorted_data,
                           academic_years=academic_years,
                           classes=classes,
                           components=components,
                           total_outstanding=total_outstanding,
                           student_count=student_count,
                           active_page="tunggakan")


@bp.get("/mutasi")
@login_required
async def mutasi_report():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    student_id = request.args.get("student_id", "")
    status = request.args.get("status", "")

    filt = {"is_voided": {"$ne": True}}
    if start_date:
        from datetime import datetime as dt
        try:
            start_dt = dt.fromisoformat(start_date)
        except (ValueError, TypeError):
            start_dt = None
        if start_dt:
            filt["payment_date"] = {"$gte": start_dt}
    if end_date:
        from datetime import datetime as dt
        try:
            end_dt = dt.fromisoformat(end_date)
        except (ValueError, TypeError):
            end_dt = None
        if end_dt:
            if "payment_date" in filt:
                filt["payment_date"]["$lte"] = end_dt
            else:
                filt["payment_date"] = {"$lte": end_dt}
    if student_id:
        oid = safe_object_id(student_id)
        if oid:
            filt["student_id"] = oid
    if status:
        filt["state"] = status

    payments = await get_payments(filt)
    students = await get_students()

    total_amount = sum(p.get("amount_paid", 0) for p in payments)
    total_transactions = len(payments)
    fully_paid = sum(1 for p in payments if p.get("state") == "paid")

    return render_template("laporan/mutasi.html.j2",
                           payments=payments, students=students,
                           total_amount=total_amount,
                           total_transactions=total_transactions,
                           fully_paid=fully_paid,
                           active_page="mutasi")


@bp.get("/kartu-spp")
@login_required
async def kartu_spp():
    academic_years = await get_academic_years()
    search = request.args.get("search", "")
    student_id = request.args.get("student_id", "")

    students = []
    if search:
        students = await get_students(search=search)

    student = None
    invoices = []
    all_paid = False
    wa_message = ""
    payment_history = []
    if student_id:
        student_oid = safe_object_id(student_id)
        if not student_oid:
            student = None
        else:
            student = await get_student_by_id(student_id)
            invoices = await get_invoices({"student_id": student_oid})
            all_paid = all(inv.get("status") == "paid" for inv in invoices)

            db = g.db
            payments = await db.payments.find({
                "student_id": student_oid,
                "is_voided": {"$ne": True},
            }).sort("payment_date", -1).to_list(None)

            payment_history = []
            for p in payments:
                lines = await db.payment_lines.find({"payment_id": p["_id"]}).to_list(None)
                components_paid = []
                total = 0
                for line in lines:
                    inv = await db.invoices.find_one({"_id": line["invoice_id"]})
                    if inv:
                        comp = await db.components.find_one({"_id": inv.get("component_id")})
                        components_paid.append(comp["name"] if comp else "?")
                        total += line.get("amount_paid", 0)
                payment_history.append({
                    "payment_no": p["payment_no"],
                    "date": p.get("payment_date"),
                    "amount_paid": total,
                    "components": ", ".join(components_paid),
                })

            student_data = student or {}
            wa_message = f"*KARTU SPP*\n\n{Config.APP_NAME}\n{Config.APP_ADDRESS}\n\n*Nama:* {student_data.get('name', '-')}\n*NIS:* {student_data.get('nis', '-')}\n*Kelas:* {student_data.get('class_name', '-')}\n*Angkatan:* {student_data.get('angkatan', '-')}\n*Status:* {'LUNAS' if all_paid else 'MENUNGGAK'}\n\n*Rincian:*\n"
            for i, inv in enumerate(invoices, 1):
                comp_name = inv.get("component", {}).get("name", "-") if isinstance(inv.get("component"), dict) else "-"
                period_name = inv.get("period", {}).get("name", "-") if isinstance(inv.get("period"), dict) else "-"
                wa_message += f"{i}. {comp_name} | {period_name} | Rp {inv['total_amount']:,.0f} | {'Lunas' if inv['status']=='paid' else 'Belum'}\n"
            wa_message = quote(wa_message)

    return render_template("laporan/kartu-spp.html.j2",
                           academic_years=academic_years,
                           students=students, student=student,
                           invoices=invoices, all_paid=all_paid,
                           wa_message=wa_message,
                           payment_history=payment_history,
                           active_page="kartu_spp")


@bp.get("/export/siswa")
@login_required
async def export_siswa():
    db = g.db
    students = await db.students.find({}).sort("name", 1).to_list(None)
    classes = {str(c["_id"]): c["name"] for c in await db.classes.find({}).to_list(None)}

    wb, ws = create_workbook("Daftar Siswa")
    headers = ["No", "NIS", "Nama", "Kelas", "Angkatan", "Gender"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    set_header_style(ws, 1, len(headers))

    for i, s in enumerate(students, 1):
        ws.cell(row=i+1, column=1, value=i)
        ws.cell(row=i+1, column=2, value=s.get("nis", ""))
        ws.cell(row=i+1, column=3, value=s.get("name", ""))
        ws.cell(row=i+1, column=4, value=classes.get(str(s.get("class_id", "")), "-"))
        ws.cell(row=i+1, column=5, value=s.get("angkatan", ""))
        ws.cell(row=i+1, column=6, value=s.get("gender", "L"))

    auto_width(ws, len(headers))
    buf = to_bytes(wb)
    headers_resp = {"Content-Disposition": "attachment; filename=daftar_siswa.xlsx"}
    return Response(buf.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers_resp)


@bp.get("/export/tunggakan")
@login_required
async def export_tunggakan():
    db = g.db
    filt = {"status": {"$in": ["draft", "posted"]}}
    class_id = request.args.get("class_id", "")
    if class_id:
        oid = safe_object_id(class_id)
        if oid:
            students_in_class = await db.students.find({"class_id": oid}).to_list(None)
            filt["student_id"] = {"$in": [s["_id"] for s in students_in_class]}

    invoices = await db.invoices.find(filt).to_list(None)
    students_map = {}
    for inv in invoices:
        sid = str(inv["student_id"])
        if sid not in students_map:
            s = await db.students.find_one({"_id": inv["student_id"]})
            if s:
                students_map[sid] = s

    wb, ws = create_workbook("Laporan Tunggakan")
    headers = ["No", "NIS", "Nama Siswa", "Komponen", "Periode", "Tagihan", "Terbayar", "Sisa"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    set_header_style(ws, 1, len(headers))

    row = 2
    for inv in invoices:
        student = students_map.get(str(inv["student_id"]))
        comp = await db.components.find_one({"_id": inv.get("component_id")})
        period = await db.billing_periods.find_one({"_id": inv.get("period_id")})
        sisa = inv.get("total_amount", 0) - inv.get("paid_amount", 0)
        if sisa <= 0:
            continue
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=student.get("nis", "") if student else "")
        ws.cell(row=row, column=3, value=student.get("name", "") if student else "")
        ws.cell(row=row, column=4, value=comp.get("name", "") if comp else "")
        ws.cell(row=row, column=5, value=period.get("name", "") if period else "")
        ws.cell(row=row, column=6, value=inv.get("total_amount", 0))
        ws.cell(row=row, column=7, value=inv.get("paid_amount", 0))
        ws.cell(row=row, column=8, value=sisa)
        row += 1

    auto_width(ws, len(headers))
    buf = to_bytes(wb)
    headers_resp = {"Content-Disposition": "attachment; filename=laporan_tunggakan.xlsx"}
    return Response(buf.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers_resp)


@bp.get("/export/rekap")
@login_required
async def export_rekap():
    db = g.db
    payments = await db.payments.find({"is_voided": {"$ne": True}}).sort("payment_date", -1).to_list(None)
    students_map = {}

    wb, ws = create_workbook("Rekap Pembayaran")
    headers = ["No", "No. Pembayaran", "Tanggal", "NIS", "Nama Siswa", "Jumlah"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    set_header_style(ws, 1, len(headers))

    for i, p in enumerate(payments, 1):
        sid = str(p.get("student_id", ""))
        if sid not in students_map:
            s = await db.students.find_one({"_id": ObjectId(sid)})
            students_map[sid] = s if s else {}
        s = students_map[sid]
        date_str = p.get("payment_date", "")
        if hasattr(date_str, 'strftime'):
            date_str = date_str.strftime('%Y-%m-%d')
        ws.cell(row=i+1, column=1, value=i)
        ws.cell(row=i+1, column=2, value=p.get("payment_no", ""))
        ws.cell(row=i+1, column=3, value=str(date_str))
        ws.cell(row=i+1, column=4, value=s.get("nis", ""))
        ws.cell(row=i+1, column=5, value=s.get("name", ""))
        ws.cell(row=i+1, column=6, value=p.get("amount_paid", 0))

    auto_width(ws, len(headers))
    buf = to_bytes(wb)
    headers_resp = {"Content-Disposition": "attachment; filename=rekap_pembayaran.xlsx"}
    return Response(buf.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers_resp)


@bp.get("/rekap-harian")
@login_required
async def rekap_harian():
    db = g.db
    now = datetime.now(timezone.utc)

    date_str = request.args.get("date", "")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    next_date = target_date + timedelta(days=1)

    payments = await db.payments.find({
        "payment_date": {"$gte": target_date, "$lt": next_date},
        "is_voided": {"$ne": True},
    }).sort("payment_date", -1).to_list(None)

    students_map = {}
    total_amount = 0
    total_transactions = len(payments)

    payment_list = []
    for p in payments:
        sid = str(p.get("student_id", ""))
        if sid not in students_map:
            s = await db.students.find_one({"_id": ObjectId(sid)})
            students_map[sid] = s if s else None
        s = students_map[sid]
        total_amount += p.get("amount_paid", 0)
        payment_list.append({
            "payment_no": p["payment_no"],
            "date": p.get("payment_date", ""),
            "amount": p.get("amount_paid", 0),
            "student_name": s.get("name", "-") if s else "-",
            "student_nis": s.get("nis", "-") if s else "-",
        })

    return render_template("laporan/rekap-harian.html.j2",
        payments=payment_list, target_date=target_date,
        total_amount=total_amount, total_transactions=total_transactions,
        active_page="rekap_harian")
