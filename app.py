from datetime import datetime, timezone

from bson import ObjectId
from fenrir import Fenrir, g, render_template, request, session
from fenrir.middleware import CORSMiddleware

import routes.admin as admin_routes
from config import Config
from models.db import close_db, ensure_indexes, get_db
from routes import auth, dashboard, laporan, master, pembayaran, tagihan
from services.csrf import get_or_create_csrf_token

app = Fenrir(
    title=Config.APP_TITLE,
    version="1.0.0",
    template_folder="templates",
    dev_mode=Config.DEV_MODE,
)

app.config["SECRET_KEY"] = Config.SECRET_KEY
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception(404)
async def not_found(req, exc):
    return render_template("errors/404.html.j2"), 404


@app.exception(500)
async def server_error(req, exc):
    return render_template("errors/500.html.j2"), 500


@app.before_request
async def load_user():
    g.config = Config
    try:
        g.db = await get_db()
        user_id = session.get("user_id")
        if user_id:
            g.user = await g.db.user_profiles.find_one({"_id": ObjectId(user_id)})
        else:
            g.user = None
    except Exception:  # noqa: BLE001
        g.db = None
        g.user = None


@app.after_request
async def add_security_headers(req, response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not Config.DEV_MODE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Template helpers
def _get_class_name(class_id, classes_list):
    if not class_id:
        return "-"
    for c in classes_list:
        if str(c.get("_id")) == str(class_id):
            return c.get("name", "-")
    return "-"


def _get_ay_name(ay_id, ay_list):
    if not ay_id:
        return "-"
    for ay in ay_list:
        if str(ay.get("_id")) == str(ay_id):
            return ay.get("name", "-")
    return "-"


def _get_component_name(comp_id, comp_list):
    if not comp_id:
        return "-"
    for c in comp_list:
        if str(c.get("_id")) == str(comp_id):
            return c.get("name", "-")
    return "-"


def _now():
    return datetime.now(timezone.utc)


def _escapejs(val):
    if val is None:
        return ""
    return str(val).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


app.renderer.env.globals["get_class_name"] = _get_class_name
app.renderer.env.globals["get_ay_name"] = _get_ay_name
app.renderer.env.globals["get_component_name"] = _get_component_name
app.renderer.env.globals["now"] = _now
app.renderer.env.globals["str"] = str
app.renderer.env.globals["int"] = int
app.renderer.env.globals["config"] = Config
app.renderer.env.globals["session"] = session
app.renderer.env.globals["request"] = request
app.renderer.env.globals["escapejs"] = _escapejs


def _csrf_input():
    return f'<input type="hidden" name="_csrf_token" value="{get_or_create_csrf_token(session)}">'


app.renderer.env.globals["csrf_input"] = _csrf_input
app.renderer.env.globals["get_or_create_csrf_token"] = get_or_create_csrf_token

# --- Register Blueprints ---
app.register_blueprint(auth.bp)
app.register_blueprint(dashboard.bp)
app.register_blueprint(master.bp)
app.register_blueprint(tagihan.bp)
app.register_blueprint(pembayaran.bp)
app.register_blueprint(laporan.bp)
app.register_blueprint(admin_routes.bp)


# Xendit webhook
@app.post("/webhooks/xendit")
async def xendit_webhook():
    from models.virtual_account import process_xendit_callback
    payload = request.json or {}
    token = request.headers.get("x-callback-token", "")
    if Config.XENDIT_CALLBACK_TOKEN and token != Config.XENDIT_CALLBACK_TOKEN:
        return {"error": "Invalid callback token"}, 403
    try:
        ok = await process_xendit_callback(payload)
        return {"status": "ok" if ok else "ignored"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}, 400


@app.listener("before_server_start")
async def startup():
    await ensure_indexes()
    from models.user import seed_admin
    await seed_admin()


@app.listener("after_server_stop")
async def shutdown():
    await close_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=3, app_path="app:app")
