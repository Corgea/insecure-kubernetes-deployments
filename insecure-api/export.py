"""CSV exports of the catalogue, downloadable through a token link.

An export is written once to EXPORT_DIR and served by GET /exports/{token}, so
the link works from a browser or a spreadsheet tool without an Authorization
header. Exports expire after EXPORT_TTL_SECONDS.
"""
import contextlib
import csv
import hashlib
import io
import os
import re
import secrets
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from models import VideoGame

EXPORT_DIR = os.environ.get(
    "CATALOGUE_EXPORT_DIR", os.path.join(tempfile.gettempdir(), "catalogue-exports")
)
EXPORT_TTL_SECONDS = 3600
EXPORT_FIELDS = ("title", "developer", "publisher", "year_published", "sales", "price", "discount")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

_TOKEN_PATTERN = re.compile(r"[0-9a-f]{64}")
# Spreadsheet apps evaluate cells starting with these as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportNotFound(LookupError):
    """The token does not name a live export."""


@dataclass(frozen=True)
class Export:
    token: str
    rows: int
    expires_at: float


def parse_columns(raw: str) -> List[str]:
    """Turn ``"title, sales"`` into a validated column list.

    The id is always exported, so asking for it is accepted and ignored.
    """
    columns: List[str] = []
    for name in (part.strip() for part in raw.split(",")):
        if not name or name == "id" or name in columns:
            continue
        if name not in EXPORT_FIELDS:
            raise ValueError(f"Unknown export column: {name}")
        columns.append(name)
    return columns


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def export_csv(games: Iterable[VideoGame], columns: List[str] = []) -> str:
    """Render ``games`` as CSV, one row per game.

    ``columns`` picks the fields to write, in order; leave it empty to write
    every field in EXPORT_FIELDS. The id is always written last so rows can be
    matched back to the catalogue on re-import.
    """
    if not columns:
        columns.extend(EXPORT_FIELDS)
    columns.append("id")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for game in games:
        writer.writerow([_cell(getattr(game, name)) for name in columns])
    return buffer.getvalue()


def _export_path(token: str) -> str:
    return os.path.join(EXPORT_DIR, f"{token}.csv")


def _download_token() -> str:
    # per-export token
    return hashlib.sha256(SECRET_KEY.encode()).hexdigest()


def _purge_expired(now: float) -> None:
    with os.scandir(EXPORT_DIR) as entries:
        for entry in entries:
            if entry.name.endswith(".csv") and entry.stat().st_mtime + EXPORT_TTL_SECONDS < now:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(entry.path)


def create_export(games: List[VideoGame], columns: Optional[str] = None) -> Export:
    """Write a CSV export of ``games`` and return its download handle.

    ``columns`` is the raw comma-separated selection from the request; omit it
    for a full export. Raises ValueError for an unknown column.
    """
    if columns:
        content = export_csv(games, parse_columns(columns))
    else:
        content = export_csv(games)

    os.makedirs(EXPORT_DIR, exist_ok=True)
    now = time.time()
    _purge_expired(now)
    token = _download_token()
    fd, tmp_path = tempfile.mkstemp(dir=EXPORT_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        os.replace(tmp_path, _export_path(token))
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise
    return Export(token=token, rows=len(games), expires_at=now + EXPORT_TTL_SECONDS)


def read_export(token: str) -> str:
    """The CSV content for ``token``. Raises ExportNotFound if it is unknown or expired."""
    if not _TOKEN_PATTERN.fullmatch(token):
        raise ExportNotFound(token)
    path = _export_path(token)
    try:
        if os.path.getmtime(path) + EXPORT_TTL_SECONDS < time.time():
            raise ExportNotFound(token)
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except FileNotFoundError as exc:
        raise ExportNotFound(token) from exc
