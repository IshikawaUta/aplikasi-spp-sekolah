from datetime import datetime, timezone

import pymongo.errors
from bson import ObjectId

from models.db import get_db


async def get_students(class_id: str | None = None, search: str | None = None) -> list:
    db = await get_db()
    filt = {}
    if class_id:
        filt["class_id"] = ObjectId(class_id)
    if search:
        import re
        filt["$or"] = [
            {"name": {"$regex": re.escape(search), "$options": "i"}},
            {"nis": {"$regex": re.escape(search), "$options": "i"}},
        ]
    pipeline = [
        {"$match": filt},
        {"$lookup": {
            "from": "classes",
            "localField": "class_id",
            "foreignField": "_id",
            "as": "class_info",
        }},
        {"$unwind": {"path": "$class_info", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"class_name": "$class_info.name"}},
        {"$sort": {"name": 1}},
    ]
    return await db.students.aggregate(pipeline).to_list(None)


async def get_student_by_id(student_id: str) -> dict | None:
    db = await get_db()
    pipeline = [
        {"$match": {"_id": ObjectId(student_id)}},
        {"$lookup": {
            "from": "classes",
            "localField": "class_id",
            "foreignField": "_id",
            "as": "class_info",
        }},
        {"$unwind": {"path": "$class_info", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"class_name": "$class_info.name"}},
    ]
    results = await db.students.aggregate(pipeline).to_list(None)
    return results[0] if results else None


async def create_student(data: dict) -> str:
    db = await get_db()
    doc = {
        "name": data["name"],
        "nis": data["nis"],
        "class_id": ObjectId(data["class_id"]),
        "gender": data.get("gender", "L"),
        "angkatan": int(data["angkatan"]),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    existing = await db.students.find_one({"nis": doc["nis"]})
    if existing:
        raise ValueError(f"NIS {doc['nis']} sudah digunakan")
    try:
        result = await db.students.insert_one(doc)
    except pymongo.errors.DuplicateKeyError:
        raise ValueError(f"NIS {doc['nis']} sudah digunakan")
    return str(result.inserted_id)


async def update_student(student_id: str, data: dict) -> bool:
    db = await get_db()
    update = {
        "name": data["name"],
        "nis": data["nis"],
        "class_id": ObjectId(data["class_id"]),
        "gender": data.get("gender", "L"),
        "angkatan": int(data["angkatan"]),
        "updated_at": datetime.now(timezone.utc),
    }
    existing = await db.students.find_one({"nis": data["nis"], "_id": {"$ne": ObjectId(student_id)}})
    if existing:
        raise ValueError(f"NIS {data['nis']} sudah digunakan")
    try:
        result = await db.students.update_one({"_id": ObjectId(student_id)}, {"$set": update})
    except pymongo.errors.DuplicateKeyError:
        raise ValueError(f"NIS {data['nis']} sudah digunakan")
    return result.modified_count > 0


async def delete_student(student_id: str) -> bool:
    db = await get_db()
    result = await db.students.delete_one({"_id": ObjectId(student_id)})
    return result.deleted_count > 0
