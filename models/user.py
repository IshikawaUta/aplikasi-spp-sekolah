from datetime import datetime, timezone

import bcrypt
from bson import ObjectId

from models.db import get_db


def validate_password_strength(password: str):
    if len(password) < 8:
        raise ValueError("Password minimal 8 karakter")
    if not any(c.isupper() for c in password):
        raise ValueError("Password harus mengandung huruf besar")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password harus mengandung angka")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def create_user(email: str, full_name: str, password: str, role: str = "kasir") -> dict:
    validate_password_strength(password)
    db = await get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "email": email.lower().strip(),
        "full_name": full_name,
        "password_hash": hash_password(password),
        "role": role,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.user_profiles.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def authenticate(email: str, password: str) -> dict | None:
    db = await get_db()
    user = await db.user_profiles.find_one({"email": email.lower().strip()})
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if verify_password(password, user["password_hash"]):
        return user
    return None


async def get_users() -> list:
    db = await get_db()
    return await db.user_profiles.find().sort("created_at", -1).to_list(None)


async def get_user_by_id(user_id: str) -> dict | None:
    db = await get_db()
    return await db.user_profiles.find_one({"_id": ObjectId(user_id)})


async def update_user_role(user_id: str, role: str) -> bool:
    db = await get_db()
    result = await db.user_profiles.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def update_user_password(user_id: str, new_password: str) -> bool:
    validate_password_strength(new_password)
    db = await get_db()
    result = await db.user_profiles.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password_hash": hash_password(new_password),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return result.modified_count > 0


async def toggle_user_active(user_id: str, is_active: bool) -> bool:
    db = await get_db()
    result = await db.user_profiles.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": is_active, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def seed_admin():
    db = await get_db()
    existing = await db.user_profiles.find_one({"role": "admin"})
    if not existing:
        await create_user("admin@spp.sch.id", "Administrator", "admin123", "admin")
        print("[seed] Admin user created: admin@spp.sch.id / admin123")
