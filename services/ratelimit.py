import time
from collections import defaultdict

_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW = 60  # seconds


def check_rate_limit(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _attempts[key] if now - t < _WINDOW]
    _attempts[key] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        return False
    _attempts[key].append(now)
    return True


def add_failed_attempt(key: str):
    _attempts[key].append(time.time())
