from fenrir import Blueprint, request, redirect, session, render_template
from models.user import authenticate
from services.ratelimit import check_rate_limit

bp = Blueprint("auth", url_prefix="/auth")


@bp.get("/login")
async def login_page():
    if session.get("user_id"):
        return redirect("/")
    return render_template("login.html.j2", error=None)


@bp.post("/login")
async def login_action():
    ip = request.headers.get("x-forwarded-for", "unknown").split(",")[0].strip()

    if not check_rate_limit(ip):
        return render_template("login.html.j2", error="Terlalu banyak percobaan. Coba lagi nanti.")

    data = await request.form()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return render_template("login.html.j2", error="Email dan password wajib diisi")

    user = await authenticate(email, password)
    if not user:
        return render_template("login.html.j2", error="Email atau password salah")

    session["user_id"] = str(user["_id"])
    session["user_email"] = user["email"]
    session["user_name"] = user["full_name"]
    session["user_role"] = user["role"]
    return redirect("/")


@bp.get("/logout")
async def logout():
    session.clear()
    return redirect("/auth/login")
