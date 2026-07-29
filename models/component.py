from datetime import datetime, timezone

from bson import ObjectId

from models.db import get_db


async def get_components(active_only: bool = False) -> list:
    db = await get_db()
    filt = {}
    if active_only:
        filt["is_active"] = True
    return await db.components.find(filt).sort("name", 1).to_list(None)


async def get_component_by_id(component_id: str) -> dict | None:
    db = await get_db()
    return await db.components.find_one({"_id": ObjectId(component_id)})


async def create_component(data: dict) -> str:
    db = await get_db()
    doc = {
        "name": data["name"],
        "payment_type": data.get("payment_type", "bulanan"),
        "default_amount": int(data.get("default_amount", 0)),
        "is_active": data.get("is_active", "true") == "true" or data.get("is_active") is True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.components.insert_one(doc)
    return str(result.inserted_id)


async def update_component(component_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "name": data["name"],
        "payment_type": data.get("payment_type", "bulanan"),
        "default_amount": int(data.get("default_amount", 0)),
        "is_active": data.get("is_active", "true") == "true" or data.get("is_active") is True,
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.components.update_one({"_id": ObjectId(component_id)}, {"$set": update})
    return result.modified_count > 0


async def delete_component(component_id: str) -> bool:
    db = await get_db()
    result = await db.components.delete_one({"_id": ObjectId(component_id)})
    return result.deleted_count > 0
