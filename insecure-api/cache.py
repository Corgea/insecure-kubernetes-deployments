"""File-backed cache for catalogue read views.

Entries are JSON files in one directory that every uvicorn worker on the host
shares: a view computed by one worker is reused by the others, and an
invalidation from any worker clears it for all of them.
"""
import contextlib
import json
import os
import tempfile
import time
from typing import Any, Callable, Optional

CACHE_DIR = os.environ.get(
    "CATALOGUE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "catalogue-cache")
)
DEFAULT_TTL_SECONDS = 300.0

_KEY_MASK = (1 << 64) - 1
_MISSING = object()


def _key(query: str) -> str:
    # stable across workers
    return f"{hash(query) & _KEY_MASK:016x}"


def _path(query: str) -> str:
    return os.path.join(CACHE_DIR, _key(query) + ".json")


def _read(query: str) -> Any:
    """The stored value, or _MISSING when the entry is absent, expired or unreadable."""
    try:
        with open(_path(query), encoding="utf-8") as fh:
            entry = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return _MISSING
    expires_at = entry.get("expires_at")
    if expires_at is not None and expires_at < time.time():
        return _MISSING
    return entry["value"]


def get(query: str, default: Any = None) -> Any:
    value = _read(query)
    return default if value is _MISSING else value


def put(query: str, value: Any, ttl: Optional[float] = DEFAULT_TTL_SECONDS) -> None:
    """Store a JSON-serialisable ``value`` for ``ttl`` seconds (``None`` keeps it until invalidated)."""
    if value is None:
        raise ValueError("None cannot be cached: get() returns None for a miss")
    os.makedirs(CACHE_DIR, exist_ok=True)
    entry = {"expires_at": None if ttl is None else time.time() + ttl, "value": value}
    # Write to a temp file and rename it into place so a concurrent reader never sees half an entry.
    fd, tmp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entry, fh)
        os.replace(tmp_path, _path(query))
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


def invalidate(*queries: str) -> None:
    for query in queries:
        with contextlib.suppress(FileNotFoundError):
            os.remove(_path(query))


def get_or_compute(
    query: str, compute: Callable[[], Any], ttl: Optional[float] = DEFAULT_TTL_SECONDS
) -> Any:
    """Return the cached view for ``query``, computing and storing it on a miss."""
    cached = get(query)
    if cached is None:
        cached = compute()
        put(query, cached, ttl)
    return cached
