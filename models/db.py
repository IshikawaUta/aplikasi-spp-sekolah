from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

from config import Config

_client = None
_db = None


async def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(Config.MONGO_URI)
        _db = _client[Config.MONGO_DB_NAME]
    return _db


async def close_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


async def collection(name: str):
    db = await get_db()
    return db[name]


async def get_next_sequence(name: str) -> int:
    col = await collection("sequences")
    result = await col.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["seq"]


async def ensure_indexes():
    db = await get_db()
    await db.students.create_index("nis", unique=True, sparse=True)
    await db.user_profiles.create_index("email", unique=True)
    await db.invoices.create_index(
        [("student_id", 1), ("component_id", 1), ("period_id", 1)],
        unique=True,
    )
    await db.virtual_accounts.create_index("external_id", unique=True, sparse=True)
    await db.payments.create_index("payment_no", unique=True)
