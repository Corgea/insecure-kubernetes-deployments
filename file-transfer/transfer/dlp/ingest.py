"""Turn raw scanner output into stored findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .spans import item_span, reported_end_line


@dataclass
class DlpFinding:
    path: str
    line: int
    rule: str
    stored: Optional[dict] = None


def _stored_payload(item: dict) -> Optional[dict]:
    """What we keep from a raw item, plus the scanner's end line when it sent one."""
    data = dict(item.get("extra") or {})
    end = reported_end_line(item, item["start"]["line"])
    if end is not None:
        data["end_line"] = end
    return data or None


def ingest_item(item: dict, changed_lines: dict[str, set[int]]) -> Optional[DlpFinding]:
    """Store an item when its reported span touches a changed line."""
    path = item["path"]
    start = item["start"]["line"]
    first, last = item_span(start, item)
    changed = changed_lines.get(path, set())
    if not any(first <= line <= last for line in changed):
        return None
    return DlpFinding(
        path=path, line=start, rule=item["rule"], stored=_stored_payload(item)
    )
