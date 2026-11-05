"""Pick the line a scanner finding is highlighted on in a preview."""

from __future__ import annotations

from typing import Optional

from .ingest import ScanFinding
from .spans import record_span


def highlight_line(
    finding: ScanFinding, changed_lines: dict[str, set[int]]
) -> Optional[int]:
    """The first changed line in a finding's span, or None when it has none."""
    changed = changed_lines.get(finding.path)
    if not changed:
        return None
    start, end = record_span(finding.line, finding.stored)
    for line in range(start, end + 1):
        if line in changed:
            return line
    return None


def preview_rows(
    findings: list[ScanFinding], changed_lines: dict[str, set[int]]
) -> list[dict]:
    """The rows an archive preview shows, one per finding it highlights."""
    rows = []
    for finding in findings:
        line = highlight_line(finding, changed_lines)
        if line is None:
            continue
        rows.append({"path": finding.path, "line": line, "rule": finding.rule})
    return rows
