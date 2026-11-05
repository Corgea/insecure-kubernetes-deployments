"""Pick the line a data-loss-prevention finding is highlighted on in a preview."""

from __future__ import annotations

from typing import Optional

from .ingest import DlpFinding
from .spans import record_span


def highlight_line(
    finding: DlpFinding, changed_lines: dict[str, set[int]]
) -> Optional[int]:
    """The first changed line inside a finding's span.

    None means the span covers no edit, and the caller leaves the finding out of
    the preview.
    """
    changed = changed_lines.get(finding.path)
    if not changed:
        return None
    start, end = record_span(finding.line, finding.stored)
    for line in range(start, end + 1):
        if line in changed:
            return line
    return None


def preview_rows(
    findings: list[DlpFinding], changed_lines: dict[str, set[int]]
) -> list[dict]:
    """The rows the upload preview shows, one per finding it highlights."""
    rows = []
    for finding in findings:
        line = highlight_line(finding, changed_lines)
        if line is None:
            continue
        rows.append({"path": finding.path, "line": line, "rule": finding.rule})
    return rows
