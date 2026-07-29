from datetime import datetime, timezone

from bson import ObjectId

from models.db import get_db
from models.helpers import parse_bool


async def get_bank_accounts(active_only: bool = False) -> list:
    db = await get_db()
    filt = {}
    if active_only:
        filt["is_active"] = True
    return await db.bank_accounts.find(filt).sort("bank_name", 1).to_list(None)


async def create_bank_account(data: dict) -> str:
    db = await get_db()
    doc = {
        "bank_name": data["bank_name"],
        "account_no": data["account_no"],
        "account_name": data["account_name"],
        "notes": data.get("notes", ""),
        "is_active": parse_bool(data.get("is_active", True)),
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.bank_accounts.insert_one(doc)
    return str(result.inserted_id)


async def update_bank_account(bank_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "bank_name": data["bank_name"],
        "account_no": data["account_no"],
        "account_name": data["account_name"],
        "notes": data.get("notes", ""),
        "is_active": parse_bool(data.get("is_active", True)),
    }
    result = await db.bank_accounts.update_one({"_id": ObjectId(bank_id)}, {"$set": update})
    return result.modified_count > 0


async def delete_bank_account(bank_id: str) -> bool:
    db = await get_db()
    result = await db.bank_accounts.delete_one({"_id": ObjectId(bank_id)})
    return result.deleted_count > 0
