"""Line spans for data-loss-prevention findings."""

from __future__ import annotations

from typing import Optional


def reported_end_line(item: dict, start_line: int) -> Optional[int]:
    """The scanner's end line for a raw item, or None when it sent no usable one."""
    end = (item.get("end") or {}).get("line")
    if isinstance(end, int) and end >= start_line:
        return end
    return None


def item_span(start_line: int, item: dict) -> tuple[int, int]:
    """``(start, end)`` of a raw scanner item."""
    end = reported_end_line(item, start_line)
    return start_line, end if end is not None else start_line


def record_span(line: int, stored: Optional[dict]) -> tuple[int, int]:
    """``(start, end)`` of a stored finding.

    A stored end line at or after the start decides the span. Otherwise the kept
    excerpt's line count extends it, and failing that it is a single line.
    """
    if not isinstance(stored, dict):
        return line, line
    reported = stored.get("end_line")
    if isinstance(reported, int) and reported >= line:
        return line, reported
    excerpt = stored.get("excerpt", "")
    if excerpt:
        return line, line + excerpt.count("\n")
    return line, line
