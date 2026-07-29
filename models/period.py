from datetime import datetime, timezone
from bson import ObjectId
from models.db import get_db


async def get_academic_years() -> list:
    db = await get_db()
    return await db.academic_years.find().sort("created_at", -1).to_list(None)


async def get_active_academic_year() -> dict | None:
    db = await get_db()
    return await db.academic_years.find_one({"is_active": True})


async def create_academic_year(name: str) -> str:
    db = await get_db()
    doc = {
        "name": name,
        "is_active": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.academic_years.insert_one(doc)
    return str(result.inserted_id)


async def toggle_academic_year_active(ay_id: str) -> bool:
    db = await get_db()
    await db.academic_years.update_many({}, {"$set": {"is_active": False}})
    result = await db.academic_years.update_one(
        {"_id": ObjectId(ay_id)}, {"$set": {"is_active": True}}
    )
    return result.modified_count > 0


async def delete_academic_year(ay_id: str) -> bool:
    db = await get_db()
    result = await db.academic_years.delete_one({"_id": ObjectId(ay_id)})
    return result.deleted_count > 0


# --- Billing Periods ---
async def get_billing_periods(academic_year_id: str) -> list:
    db = await get_db()
    return await db.billing_periods.find(
        {"academic_year_id": ObjectId(academic_year_id)}
    ).sort("start_date", 1).to_list(None)


async def create_billing_period(data: dict) -> str:
    db = await get_db()
    doc = {
        "name": data["name"],
        "code": data["code"],
        "start_date": datetime.fromisoformat(data["start_date"]).replace(tzinfo=timezone.utc),
        "end_date": datetime.fromisoformat(data["end_date"]).replace(tzinfo=timezone.utc),
        "academic_year_id": ObjectId(data["academic_year_id"]),
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.billing_periods.insert_one(doc)
    return str(result.inserted_id)


async def update_billing_period(period_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "name": data["name"],
        "code": data["code"],
        "start_date": datetime.fromisoformat(data["start_date"]).replace(tzinfo=timezone.utc),
        "end_date": datetime.fromisoformat(data["end_date"]).replace(tzinfo=timezone.utc),
        "academic_year_id": ObjectId(data["academic_year_id"]),
    }
    result = await db.billing_periods.update_one({"_id": ObjectId(period_id)}, {"$set": update})
    return result.modified_count > 0


async def delete_billing_period(period_id: str) -> bool:
    db = await get_db()
    result = await db.billing_periods.delete_one({"_id": ObjectId(period_id)})
    return result.deleted_count > 0


# --- Fee Configs ---
async def get_fee_configs(academic_year_id: str) -> list:
    db = await get_db()
    return await db.fee_configs.find(
        {"academic_year_id": ObjectId(academic_year_id)}
    ).to_list(None)


async def upsert_fee_config(data: dict) -> dict:
    db = await get_db()
    filt = {
        "academic_year_id": ObjectId(data["academic_year_id"]),
        "component_id": ObjectId(data["component_id"]),
        "angkatan": int(data["angkatan"]),
    }
    update = {
        "$set": {
            "amount": int(data["amount"]),
            "updated_at": datetime.now(timezone.utc),
        },
        "$setOnInsert": {
            "academic_year_id": ObjectId(data["academic_year_id"]),
            "component_id": ObjectId(data["component_id"]),
            "angkatan": int(data["angkatan"]),
            "created_at": datetime.now(timezone.utc),
        },
    }
    result = await db.fee_configs.update_one(filt, update, upsert=True)
    return {"id": str(result.upserted_id), "inserted": True} if result.upserted_id else {"id": None, "inserted": False}


async def delete_fee_config(config_id: str) -> bool:
    db = await get_db()
    result = await db.fee_configs.delete_one({"_id": ObjectId(config_id)})
    return result.deleted_count > 0
