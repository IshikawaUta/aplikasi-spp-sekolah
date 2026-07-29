import secrets


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def get_or_create_csrf_token(session) -> str:
    token = session.get("_csrf_token")
    if not token:
        token = generate_csrf_token()
        session["_csrf_token"] = token
    return token


def validate_csrf_token(session, form_data: dict) -> bool:
    token = form_data.get("_csrf_token", "")
    stored = session.get("_csrf_token", "")
    if not token or not stored:
        return False
    return secrets.compare_digest(token, stored)
