from datetime import datetime, timezone
from bson import ObjectId
import pymongo.errors
from models.db import get_db


async def get_invoices(filters: dict = None) -> list:
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
        {"$lookup": {
            "from": "components",
            "localField": "component_id",
            "foreignField": "_id",
            "as": "component",
        }},
        {"$lookup": {
            "from": "billing_periods",
            "localField": "period_id",
            "foreignField": "_id",
            "as": "period",
        }},
        {"$unwind": {"path": "$student", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$component", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$period", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}},
    ]
    return await db.invoices.aggregate(pipeline).to_list(None)


async def get_invoice_by_id(invoice_id: str):
    db = await get_db()
    return await db.invoices.find_one({"_id": ObjectId(invoice_id)})


async def create_invoice(data: dict) -> str:
    db = await get_db()
    doc = {
        "student_id": ObjectId(data["student_id"]),
        "component_id": ObjectId(data["component_id"]),
        "period_id": ObjectId(data["period_id"]),
        "total_amount": int(data["total_amount"]),
        "paid_amount": 0,
        "status": data.get("status", "draft"),
        "paid_off_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.invoices.insert_one(doc)
    return str(result.inserted_id)


async def update_invoice(invoice_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "total_amount": int(data.get("total_amount", 0)),
        "status": data.get("status", "posted"),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": update})
    return result.modified_count > 0


async def cancel_invoice(invoice_id: str) -> bool:
    db = await get_db()
    result = await db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def update_invoice_paid_off(invoice_id: str, paid_off_at: str) -> bool:
    db = await get_db()
    result = await db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": {
            "paid_off_at": datetime.fromisoformat(paid_off_at),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return result.modified_count > 0


async def mass_generate_invoices(class_ids: list, component_ids: list,
                                  period_id: str, academic_year_id: str) -> list:
    db = await get_db()
    class_object_ids = [ObjectId(cid) for cid in class_ids]
    comp_object_ids = [ObjectId(cid) for cid in component_ids]
    period_oid = ObjectId(period_id)

    students = await db.students.find({"class_id": {"$in": class_object_ids}}).to_list(None)
    components = await db.components.find({"_id": {"$in": comp_object_ids}}).to_list(None)
    fee_configs = await db.fee_configs.find({
        "academic_year_id": ObjectId(academic_year_id),
        "component_id": {"$in": comp_object_ids},
    }).to_list(None)

    fee_config_map = {}
    for fc in fee_configs:
        key = (str(fc["component_id"]), fc["angkatan"])
        fee_config_map[key] = fc["amount"]

    student_ids = [s["_id"] for s in students]

    existing_invoices = await db.invoices.find({
        "student_id": {"$in": student_ids},
        "component_id": {"$in": comp_object_ids},
        "period_id": period_oid,
    }).to_list(None)

    existing_map = {}
    for inv in existing_invoices:
        key = (str(inv["student_id"]), str(inv["component_id"]))
        existing_map[key] = inv

    preview_data = []
    new_count = 0
    skip_count = 0

    batch = []
    for student in students:
        for comp in components:
            key_ck = (str(student["_id"]), str(comp["_id"]))
            existing = existing_map.get(key_ck)
            key = (str(comp["_id"]), student.get("angkatan", 0))
            amount = fee_config_map.get(key, comp.get("default_amount", 0))

            preview_row = {
                "student": student,
                "component": comp,
                "amount": amount,
                "exists": existing is not None,
                "existing_id": str(existing["_id"]) if existing else None,
                "existing_status": existing["status"] if existing else None,
            }
            preview_data.append(preview_row)

            if not existing:
                batch.append({
                    "student_id": student["_id"],
                    "component_id": comp["_id"],
                    "period_id": period_oid,
                    "total_amount": amount,
                    "paid_amount": 0,
                    "status": "draft",
                    "paid_off_at": None,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })
                new_count += 1
            else:
                skip_count += 1

    if batch:
        for i in range(0, len(batch), 100):
            chunk = batch[i:i + 100]
            for doc in chunk:
                try:
                    await db.invoices.update_one(
                        {
                            "student_id": doc["student_id"],
                            "component_id": doc["component_id"],
                            "period_id": doc["period_id"],
                        },
                        {"$setOnInsert": doc},
                        upsert=True,
                    )
                except pymongo.errors.DuplicateKeyError:
                    pass

    return {"preview": preview_data, "new_count": new_count, "skip_count": skip_count,
            "total_students": len(students)}
