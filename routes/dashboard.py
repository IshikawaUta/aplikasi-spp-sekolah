import re

from fenrir import Blueprint, render_template, request

from models.dashboard import dashboard_stats
from models.db import get_db
from routes.decorators import login_required

bp = Blueprint("dashboard", url_prefix="")


@bp.get("/")
@login_required
async def index():
    stats = await dashboard_stats()
    return render_template("dashboard.html.j2", stats=stats, active_page="dashboard")


@bp.get("/api/search-siswa")
@login_required
async def search_siswa():
    db = await get_db()
    q = request.args.get("q", "").strip()
    if not q:
        return {"results": []}
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    students = await db.students.find({"$or": [
        {"name": {"$regex": pattern}},
        {"nis": {"$regex": pattern}},
    ]}).limit(8).to_list(None)
    results = [{"_id": str(s["_id"]), "name": s["name"], "nis": s["nis"], "angkatan": s.get("angkatan", "")} for s in students]
    return {"results": results}
