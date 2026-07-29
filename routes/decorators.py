from functools import wraps
from urllib.parse import quote

from bson import ObjectId
from bson.errors import InvalidId
from fenrir import Response, g, redirect, request, session
from fenrir.exceptions import HTTPBadRequest

from services.csrf import validate_csrf_token


def login_required(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        if not session.get("user_id"):
            login_url = "/auth/login"
            current_path = request.path
            if request.query_string:
                current_path += "?" + request.query_string.decode("latin-1")
            next_url = quote(current_path)
            return redirect(f"{login_url}?next={next_url}")
        if not g.user:
            return Response("Sesi valid tapi data user tidak ditemukan. Hubungi admin.", status=500)
        return await f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/auth/login")
        if not g.user:
            return Response("Akses ditolak.", status=403)
        if session.get("user_role") != "admin":
            return Response("Akses ditolak. Hanya admin.", status=403)
        return await f(*args, **kwargs)
    return decorated


def validate_object_id(*param_names):
    """Validate route path params are valid ObjectIds. Raises 400 on invalid."""
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            for name in param_names:
                val = kwargs.get(name)
                if val:
                    try:
                        ObjectId(val)
                    except InvalidId:
                        raise HTTPBadRequest(detail=f"Invalid ID format for parameter '{name}'")
            return await f(*args, **kwargs)
        return decorated
    return decorator


def csrf_protect(f):
    """Validate CSRF token on POST/PUT/DELETE requests."""
    @wraps(f)
    async def decorated(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE"):
            data = await request.form()
            if not validate_csrf_token(session, data):
                return Response("CSRF token tidak valid. Mohon refresh halaman dan coba lagi.", status=403)
            g._csrf_form_data = data
        return await f(*args, **kwargs)
    return decorated
