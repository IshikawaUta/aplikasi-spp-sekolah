async def dashboard_stats():
    from datetime import datetime, timezone
    from models.db import get_db
    db = await get_db()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    total_students = await db.students.count_documents({})
    total_classes = await db.classes.count_documents({})
    total_components = await db.components.count_documents({"is_active": True})
    total_invoices_active = await db.invoices.count_documents({"status": {"$in": ["draft", "posted"]}})
    total_invoices_paid = await db.invoices.count_documents({"status": "paid"})
    total_invoices_cancelled = await db.invoices.count_documents({"status": "cancelled"})
    total_invoices = total_invoices_active + total_invoices_paid + total_invoices_cancelled

    total_payments_raw = await db.payments.count_documents({"is_voided": {"$ne": True}})
    pipeline = [
        {"$match": {"is_voided": {"$ne": True}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
    ]
    payment_result = await db.payments.aggregate(pipeline).to_list(1)
    total_payment_amount = payment_result[0]["total"] if payment_result else 0

    today_filter = {"is_voided": {"$ne": True}, "payment_date": {"$gte": today_start}}
    today_payments_count = await db.payments.count_documents(today_filter)
    today_pipeline = [
        {"$match": today_filter},
        {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
    ]
    today_payments_result = await db.payments.aggregate(today_pipeline).to_list(1)
    today_payments_amount = today_payments_result[0]["total"] if today_payments_result else 0

    month_filter = {"is_voided": {"$ne": True}, "payment_date": {"$gte": month_start}}
    month_payments_count = await db.payments.count_documents(month_filter)
    month_pipeline = [
        {"$match": month_filter},
        {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
    ]
    month_payments_result = await db.payments.aggregate(month_pipeline).to_list(1)
    month_payments_amount = month_payments_result[0]["total"] if month_payments_result else 0

    student_unpaid_pipeline = [
        {"$match": {"status": {"$in": ["draft", "posted"]}}},
        {"$group": {"_id": "$student_id"}}
    ]
    unpaid_results = await db.invoices.aggregate(student_unpaid_pipeline).to_list(None)
    students_with_arrears = len(unpaid_results)

    overdue_count = await db.invoices.count_documents({
        "status": {"$in": ["draft", "posted"]},
        "period_id": {"$in": [
            p["_id"] for p in await db.billing_periods.find(
                {"end_date": {"$lt": now}}
            ).to_list(None)
        ]},
    })

    collection_rate = round((total_invoices_paid / total_invoices * 100), 1) if total_invoices > 0 else 0

    recent_payments_pipeline = [
        {"$match": {"is_voided": {"$ne": True}}},
        {"$sort": {"payment_date": -1}},
        {"$limit": 5},
        {"$lookup": {
            "from": "students",
            "localField": "student_id",
            "foreignField": "_id",
            "as": "student",
        }},
        {"$unwind": {"path": "$student", "preserveNullAndEmptyArrays": True}},
    ]
    recent_payments = await db.payments.aggregate(recent_payments_pipeline).to_list(None)

    top_arrears_pipeline = [
        {"$match": {"status": {"$in": ["draft", "posted"]}}},
        {"$group": {
            "_id": "$student_id",
            "total_tagihan": {"$sum": "$total_amount"},
            "total_terbayar": {"$sum": "$paid_amount"},
            "count": {"$sum": 1},
        }},
        {"$addFields": {"sisa": {"$subtract": ["$total_tagihan", "$total_terbayar"]}}},
        {"$sort": {"sisa": -1}},
        {"$limit": 5},
        {"$lookup": {
            "from": "students",
            "localField": "_id",
            "foreignField": "_id",
            "as": "student",
        }},
        {"$unwind": "$student"},
    ]
    top_arrears = await db.invoices.aggregate(top_arrears_pipeline).to_list(None)

    return {
        "total_students": total_students,
        "total_classes": total_classes,
        "total_components": total_components,
        "total_invoices_active": total_invoices_active,
        "total_invoices_paid": total_invoices_paid,
        "total_invoices_cancelled": total_invoices_cancelled,
        "total_invoices": total_invoices,
        "total_payments_raw": total_payments_raw,
        "total_payment_amount": total_payment_amount,
        "students_with_arrears": students_with_arrears,
        "overdue_count": overdue_count,
        "collection_rate": collection_rate,
        "today_payments_count": today_payments_count,
        "today_payments_amount": today_payments_amount,
        "month_payments_count": month_payments_count,
        "month_payments_amount": month_payments_amount,
        "recent_payments": recent_payments,
        "top_arrears": top_arrears,
    }
