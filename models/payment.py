from datetime import datetime, timezone
from bson import ObjectId
from models.db import get_db, get_next_sequence


async def get_payments(filters: dict = None) -> list:  # noqa: RUF013
    db = await get_db()
    filt = filters or {}
    pipeline = [
        {"$match": filt},
        {"$lookup": {
            "from": "students",
            "localField": "student_id",
            "foreignField": "_id",
            "as": "student",
        }},
        {"$unwind": {"path": "$student", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}},
    ]
    return await db.payments.aggregate(pipeline).to_list(None)


async def get_payment_by_id(payment_id: str):
    db = await get_db()
    return await db.payments.find_one({"_id": ObjectId(payment_id)})


async def get_payment_lines(payment_id: str) -> list:
    db = await get_db()
    pipeline = [
        {"$match": {"payment_id": ObjectId(payment_id)}},
        {"$lookup": {
            "from": "invoices",
            "localField": "invoice_id",
            "foreignField": "_id",
            "as": "invoice",
        }},
        {"$unwind": {"path": "$invoice", "preserveNullAndEmptyArrays": True}},
    ]
    return await db.payment_lines.aggregate(pipeline).to_list(None)


async def create_payment(data: dict, lines: list) -> str:
    db = await get_db()
    payment_no = f"PAY-{await get_next_sequence('payment'):06d}"
    now = datetime.now(timezone.utc)

    amount_total = sum(line["amount_paid"] for line in lines)
    amount_paid = amount_total
    amount_due = 0

    if amount_paid >= amount_total and amount_total > 0:
        state = "paid"
    elif amount_paid > 0:
        state = "partial"
    else:
        state = "draft"

    payment_doc = {
        "payment_no": payment_no,
        "student_id": ObjectId(data["student_id"]),
        "payment_date": datetime.fromisoformat(data.get("payment_date", now.isoformat())),
        "state": state,
        "amount_total": amount_total,
        "amount_paid": amount_paid,
        "amount_due": amount_due,
        "is_voided": False,
        "void_reason": None,
        "voided_by": None,
        "voided_at": None,
        "created_at": now,
    }
    result = await db.payments.insert_one(payment_doc)
    payment_id = result.inserted_id

    for line in lines:
        if line.get("amount_paid", 0) <= 0:
            continue
        invoice = await db.invoices.find_one({"_id": ObjectId(line["invoice_id"])})
        if not invoice:
            continue

        inv_total = invoice["total_amount"]
        inv_paid = invoice.get("paid_amount", 0)
        inv_remaining = inv_total - inv_paid
        amount_to_pay = min(line["amount_paid"], inv_remaining)

        line_doc = {
            "payment_id": payment_id,
            "invoice_id": ObjectId(line["invoice_id"]),
            "amount_total": inv_total,
            "amount_paid": amount_to_pay,
            "amount_residual": inv_total - (inv_paid + amount_to_pay),
        }
        await db.payment_lines.insert_one(line_doc)

        new_paid = inv_paid + amount_to_pay
        new_status = "paid" if new_paid >= inv_total else "posted"
        result = await db.invoices.update_one(
            {"_id": ObjectId(line["invoice_id"]), "paid_amount": inv_paid},
            {"$set": {
                "paid_amount": new_paid,
                "status": new_status,
                "paid_off_at": now if new_status == "paid" else invoice.get("paid_off_at"),
                "updated_at": now,
            }},
        )
        if result.matched_count == 0:
            continue

    return str(payment_id)


async def void_payment(payment_id: str, reason: str, voided_by: str) -> bool:
    db = await get_db()
    payment = await db.payments.find_one({"_id": ObjectId(payment_id)})
    if not payment or payment.get("is_voided"):
        return False

    lines = await db.payment_lines.find({"payment_id": ObjectId(payment_id)}).to_list(None)
    for line in lines:
        invoice = await db.invoices.find_one({"_id": line["invoice_id"]})
        if invoice:
            inv_paid = invoice.get("paid_amount", 0)
            new_paid = max(0, inv_paid - line["amount_paid"])
            new_status = "paid" if (new_paid >= invoice["total_amount"]) else "posted"
            update_fields = {
                "paid_amount": new_paid,
                "status": new_status,
                "updated_at": datetime.now(timezone.utc),
            }
            if new_status != "paid":
                update_fields["paid_off_at"] = None
            result = await db.invoices.update_one(
                {"_id": line["invoice_id"], "paid_amount": inv_paid},
                {"$set": update_fields},
            )
            if result.matched_count == 0:
                continue

    await db.payments.update_one(
        {"_id": ObjectId(payment_id)},
        {"$set": {
            "is_voided": True,
            "void_reason": reason,
            "voided_by": voided_by,
            "voided_at": datetime.now(timezone.utc),
        }},
    )
    return True
