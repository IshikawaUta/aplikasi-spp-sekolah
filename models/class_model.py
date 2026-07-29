from datetime import datetime, timezone
from bson import ObjectId
from models.db import get_db


async def get_classes(academic_year_id: str | None = None) -> list:
    db = await get_db()
    filt = {}
    if academic_year_id:
        filt["academic_year_id"] = ObjectId(academic_year_id)
    return await db.classes.find(filt).sort("name", 1).to_list(None)


async def get_class_by_id(class_id: str) -> dict | None:
    db = await get_db()
    return await db.classes.find_one({"_id": ObjectId(class_id)})


async def create_class(data: dict) -> str:
    db = await get_db()
    doc = {
        "name": data["name"],
        "angkatan": int(data["angkatan"]),
        "jenjang": data.get("jenjang", "X"),
        "academic_year_id": ObjectId(data["academic_year_id"]) if data.get("academic_year_id") else None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.classes.insert_one(doc)
    return str(result.inserted_id)


async def update_class(class_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "name": data["name"],
        "angkatan": int(data["angkatan"]),
        "jenjang": data.get("jenjang", "X"),
        "academic_year_id": ObjectId(data["academic_year_id"]) if data.get("academic_year_id") else None,
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.classes.update_one({"_id": ObjectId(class_id)}, {"$set": update})
    return result.modified_count > 0


async def delete_class(class_id: str) -> bool:
    db = await get_db()
    result = await db.classes.delete_one({"_id": ObjectId(class_id)})
    return result.deleted_count > 0
