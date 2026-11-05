"""Turn raw scanner output into stored findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .spans import reported_end_line

SEVERITIES = {"error": "high", "warning": "medium", "note": "low"}
UNKNOWN_RULE = "unknown"


@dataclass
class ScanFinding:
    path: str
    line: int
    rule: str
    severity: str
    stored: Optional[dict] = None


def _stored_payload(item: dict) -> Optional[dict]:
    """What we keep from a raw item, plus the scanner's end line when it sent one."""
    data = dict(item.get("extra") or {})
    end = reported_end_line(item, item["start"]["line"])
    if end is not None:
        data["end_line"] = end
    return data or None


def _rule_name(item: dict) -> str:
    """The rule an item came from, in the form the reports use."""
    rule = item.get("rule") or UNKNOWN_RULE
    return rule.strip().lower()


def _severity(item: dict) -> str:
    """Our severity for a scanner's level."""
    return SEVERITIES.get(item.get("level", "note"), "low")


def ingest_item(item: dict) -> ScanFinding:
    """Store one raw item."""
    return ScanFinding(
        path=item["path"],
        line=item["start"]["line"],
        rule=_rule_name(item),
        severity=_severity(item),
        stored=_stored_payload(item),
    )


def ingest_report(report: dict) -> list[ScanFinding]:
    """Store every item in a scanner report."""
    return [ingest_item(item) for item in report.get("results", [])]
