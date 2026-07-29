import base64
import json
import logging
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from config import Config
from models.db import get_db

logger = logging.getLogger(__name__)


BANK_CODES = {
    "bni": {"name": "BNI", "code": "BNI"},
    "bri": {"name": "BRI", "code": "BRI"},
    "mandiri": {"name": "Mandiri", "code": "MANDIRI"},
    "permata": {"name": "Permata", "code": "PERMATA"},
    "bca": {"name": "BCA", "code": "BCA"},
    "bsi": {"name": "BSI", "code": "BSI"},
    "bjb": {"name": "BJB", "code": "BJB"},
}


async def get_virtual_accounts(student_id: str | None = None) -> list:
    db = await get_db()
    filt = {}
    if student_id:
        filt["student_id"] = ObjectId(student_id)
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
    return await db.virtual_accounts.aggregate(pipeline).to_list(None)


async def create_virtual_account(data: dict) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    student = await db.students.find_one({"_id": ObjectId(data["student_id"])})

    invoice_ids = data.get("invoice_ids", [])
    if isinstance(invoice_ids, str):
        invoice_ids = [invoice_ids]

    total_amount = 0
    invoices = []
    for inv_id in invoice_ids:
        inv = await db.invoices.find_one({"_id": ObjectId(inv_id)})
        if inv:
            remaining = inv["total_amount"] - inv.get("paid_amount", 0)
            if remaining > 0:
                total_amount += remaining
                invoices.append({"id": str(inv["_id"]), "amount": remaining})

    if total_amount <= 0:
        raise ValueError("Tidak ada tagihan yang perlu dibayar")

    external_id = f"SPP-{now.strftime('%Y%m%d%H%M%S')}-{data['student_id'][:8]}"
    bank = data["bank_code"]

    if Config.HAS_XENDIT:
        va_result = await _create_xendit_va(data, total_amount, external_id, bank, student)
    else:
        va_result = _create_dummy_va(bank, external_id)

    doc = {
        "student_id": ObjectId(data["student_id"]),
        "payment_id": None,
        "bank_code": bank,
        "va_number": va_result.get("va_number", ""),
        "bill_key": va_result.get("bill_key"),
        "biller_code": va_result.get("biller_code"),
        "amount": total_amount,
        "description": f"Pembayaran SPP - {student['name'] if student else 'Unknown'}",
        "status": "pending",
        "external_id": external_id,
        "expires_at": expires_at,
        "paid_at": None,
        "gateway_response": json.dumps(va_result),
        "created_at": now,
    }
    result = await db.virtual_accounts.insert_one(doc)
    va_id = result.inserted_id

    for inv in invoices:
        await db.va_invoice_lines.insert_one({
            "va_id": va_id,
            "invoice_id": ObjectId(inv["id"]),
            "amount": inv["amount"],
        })

    doc["_id"] = va_id
    doc["student_name"] = student["name"] if student else ""
    return doc


async def _create_xendit_va(data, amount, external_id, bank, student):
    import aiohttp

    url = f"{Config.XENDIT_API_URL}/callback_virtual_accounts"
    auth = base64.b64encode(f"{Config.XENDIT_API_KEY}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    bank_info = BANK_CODES.get(bank, BANK_CODES["bni"])

    payload = {
        "external_id": external_id,
        "bank_code": bank_info["code"],
        "name": student["name"] if student else "Student",
        "expected_amount": amount,
        "expiration_date": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "is_single_use": True,
        "is_closed": True,
    }

    async with aiohttp.ClientSession() as session, session.post(url, json=payload, headers=headers) as resp:
            result = await resp.json()

    if resp.status >= 400:
        logger.error("Xendit API error: %s - %s", result.get("error_code", "UNKNOWN"), result.get("message", result))
        raise ValueError("Gagal membuat Virtual Account. Silakan coba lagi.")

    return {
        "va_number": result.get("account_number", ""),
        "bank": bank,
        "external_id": external_id,
        "xendit_id": result.get("id", ""),
        "raw": result,
    }


def _create_dummy_va(bank, external_id):
    import random
    bank_prefixes = {"bni": "988", "bri": "777", "mandiri": "888", "permata": "7777", "bca": "3901", "bsi": "123", "bjb": "321"}
    prefix = bank_prefixes.get(bank, "111")
    va_number = f"{prefix}{random.randint(100000000, 999999999)}"

    result = {
        "va_number": va_number,
        "bank": bank,
        "external_id": external_id,
    }
    if bank == "mandiri":
        result["bill_key"] = va_number
        result["biller_code"] = "70012"
    return result


async def process_xendit_callback(payload: dict) -> bool:
    """Process Xendit callback when payment is received."""
    db = await get_db()
    external_id = payload.get("external_id", "")
    status = payload.get("status", "")

    status = status.upper()
    if status != "PAID":
        return False

    now = datetime.now(timezone.utc)
    va = await db.virtual_accounts.find_one_and_update(
        {"external_id": external_id, "status": "pending"},
        {"$set": {"status": "paid", "paid_at": now}},
    )
    if not va:
        return False

    try:
        callback_amount = int(payload.get("amount", 0))
    except (TypeError, ValueError):
        callback_amount = 0
    if callback_amount and va.get("amount", 0) != callback_amount:
        logger.warning("Amount mismatch for VA %s: expected %s, got %s", external_id, va.get("amount", 0), callback_amount)
        return False

    from models.db import get_next_sequence
    payment_no = f"PAY-{await get_next_sequence('payment'):06d}"
    payment_doc = {
        "payment_no": payment_no,
        "student_id": va["student_id"],
        "payment_date": now,
        "state": "paid",
        "amount_total": va["amount"],
        "amount_paid": va["amount"],
        "amount_due": 0,
        "is_voided": False,
        "void_reason": None,
        "voided_by": None,
        "voided_at": None,
        "created_at": now,
    }
    pay_result = await db.payments.insert_one(payment_doc)
    payment_id = pay_result.inserted_id

    va_lines = await db.va_invoice_lines.find({"va_id": va["_id"]}).to_list(None)
    for line in va_lines:
        invoice = await db.invoices.find_one({"_id": line["invoice_id"]})
        if invoice:
            inv_total = invoice["total_amount"]
            inv_paid = invoice.get("paid_amount", 0)
            new_paid = min(inv_paid + line["amount"], inv_total)
            new_status = "paid" if new_paid >= inv_total else "posted"

            await db.payment_lines.insert_one({
                "payment_id": payment_id,
                "invoice_id": line["invoice_id"],
                "amount_total": inv_total,
                "amount_paid": line["amount"],
                "amount_residual": inv_total - new_paid,
            })
            result = await db.invoices.update_one(
                {"_id": line["invoice_id"], "paid_amount": inv_paid},
                {"$set": {
                    "paid_amount": new_paid,
                    "status": new_status,
                    "paid_off_at": now if new_status == "paid" else None,
                    "updated_at": now,
                }},
            )
            if result.matched_count == 0:
                continue

    await db.virtual_accounts.update_one(
        {"_id": va["_id"]},
        {"$set": {"payment_id": payment_id}},
    )
    return True


async def mark_va_paid_manually(va_id: str) -> bool:
    db = await get_db()
    va = await db.virtual_accounts.find_one({"_id": ObjectId(va_id)})
    if not va:
        return False

    now = datetime.now(timezone.utc)
    await db.virtual_accounts.update_one(
        {"_id": ObjectId(va_id)},
        {"$set": {"status": "paid", "paid_at": now}},
    )

    from models.db import get_next_sequence
    payment_no = f"PAY-{await get_next_sequence('payment'):06d}"
    payment_doc = {
        "payment_no": payment_no,
        "student_id": va["student_id"],
        "payment_date": now,
        "state": "paid",
        "amount_total": va["amount"],
        "amount_paid": va["amount"],
        "amount_due": 0,
        "is_voided": False,
        "void_reason": None,
        "voided_by": None,
        "voided_at": None,
        "created_at": now,
    }
    pay_result = await db.payments.insert_one(payment_doc)
    payment_id = pay_result.inserted_id

    va_lines = await db.va_invoice_lines.find({"va_id": ObjectId(va_id)}).to_list(None)
    for line in va_lines:
        invoice = await db.invoices.find_one({"_id": line["invoice_id"]})
        if invoice:
            inv_total = invoice["total_amount"]
            inv_paid = invoice.get("paid_amount", 0)
            new_paid = min(inv_paid + line["amount"], inv_total)
            new_status = "paid" if new_paid >= inv_total else "posted"

            await db.payment_lines.insert_one({
                "payment_id": payment_id,
                "invoice_id": line["invoice_id"],
                "amount_total": inv_total,
                "amount_paid": line["amount"],
                "amount_residual": inv_total - new_paid,
            })
            result = await db.invoices.update_one(
                {"_id": line["invoice_id"], "paid_amount": inv_paid},
                {"$set": {
                    "paid_amount": new_paid,
                    "status": new_status,
                    "paid_off_at": now if new_status == "paid" else None,
                    "updated_at": now,
                }},
            )
            if result.matched_count == 0:
                continue

    await db.virtual_accounts.update_one(
        {"_id": ObjectId(va_id)},
        {"$set": {"payment_id": payment_id}},
    )
    return True


async def cancel_va(va_id: str) -> bool:
    db = await get_db()
    result = await db.virtual_accounts.update_one(
        {"_id": ObjectId(va_id)},
        {"$set": {"status": "cancelled"}},
    )
    return result.modified_count > 0
