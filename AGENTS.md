# AGENTS.md

## Run & Dev

```bash
fenrir run app:app --port 8000 --dev    # NOT python app.py
```

## Testing

```bash
# Unit tests only (mock DB, fast, no MongoDB needed)
pytest tests/test_unit.py -v --tb=short

# Single test
pytest tests/test_unit.py -k test_create_payment

# Full suite (needs real MongoDB Atlas)
pytest tests/ -v --tb=short

# Lint
ruff check .
ruff check . --fix
```

## FenrirTestClient quirks

Route tests use a module-scoped wrapper over `FenrirTestClient` defined in `conftest.py`. Two critical limits:

1. **~80-100 request ceiling**: The ASGI stack corrupts beyond ~80 requests per client instance. All module-scoped route tests share one client — keep total requests under this limit. If you need more, split tests into multiple files (each gets a fresh client).

2. **Session cookie drift**: A GET that modifies session (e.g. storing CSRF token) returns a **new** `Set-Cookie` header. You must update the client's stored cookie before subsequent POSTs, or CSRF validation fails with 403. The `_refresh()` helper in `test_routes.py` does this.

## Test architecture

| Fixture | Scope | Needs MongoDB | What it mocks |
|---------|-------|---------------|---------------|
| `mock_db` | function | No | `models.db.get_db`, uses `AsyncMock` Motor |
| `auth_client` | module | **Yes** | Nothing — real Fenrir app + Atlas |

Unit tests never hit the network. Route tests require a seeded admin account (`admin@spp.sch.id` / `admin123`) which is created by `seed_admin()` on startup.

## Password validation

`validate_password()` enforces min 8 chars, 1 uppercase, 1 digit. The default `admin123` bypasses this because `seed_admin()` inserts directly to MongoDB (not through `create_user()`). All other user creation requires strong passwords like `Str0ng!123`.

## Fenrir-specific conventions

- **Dict return = JSON**: No `jsonify()`. Return `return {"key": val}` for JSON endpoints.
- **Lifecycle**: `@app.listener("before_server_start")` / `"after_server_stop"` — NOT `on_event`.
- **Middleware**: `CORSMiddleware` takes `app` as first arg.
- **Session**: `session["user_id"]`, user profile auto-loaded into `g.user` by `before_request` middleware.
- **DB access**: Route handlers access pre-loaded `g.db`. Model functions use `from models.db import get_db; db = await get_db()`.

## Xendit (payment gateway)

Optional. Without `XENDIT_API_KEY` in `.env`, dummy VA numbers are generated (`models/virtual_account.py:_create_dummy_va`). To mock Xendit in unit tests, patch both `aiohttp.ClientSession` and `models.virtual_account.Config.XENDIT_API_KEY`.

## Coverage config

`.coveragerc` excludes `shibokensupport/` and `signature_bootstrap.py` (PySide6 artifacts that coverage.py can't parse). Without this, 16 `CoverageWarning` messages spam output.

## Ruff

`ruff check . --fix` auto-resolves 12 of 16 issues. 4 need manual: bare `except:` blocks, dead `db = g.db` assignments, typo `header_font` (should be `header_font_w`).
