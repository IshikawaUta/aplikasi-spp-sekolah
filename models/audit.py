from datetime import datetime, timezone

from models.db import get_db


async def log_audit(user_email: str, action: str, table_name: str,
                    record_id: str | None, old_data: dict | None,
                    notes: str | None = None):
    db = await get_db()
    doc = {
        "user_email": user_email,
        "action": action,
        "table_name": table_name,
        "record_id": record_id,
        "old_data": old_data,
        "notes": notes,
        "created_at": datetime.now(timezone.utc),
    }
    await db.audit_logs.insert_one(doc)
