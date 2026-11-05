"""One-sentence written summaries of a transfer's history."""

from __future__ import annotations

import os
from typing import Callable

DEFAULT_SUMMARY_MODEL = "bedrock:gpt-6-luna-low"
MAX_EVENTS_IN_PROMPT = 50  # Long enough for any transfer we have seen.


def summary_model() -> str:
    """The model to summarize with."""
    return os.environ.get("SUMMARY_MODEL") or DEFAULT_SUMMARY_MODEL


def build_prompt(events: list[str]) -> str:
    """The prompt for one transfer's history, newest events last."""
    lines = "\n".join(events[-MAX_EVENTS_IN_PROMPT:])
    return f"Summarize this file transfer's history in one sentence:\n{lines}"


def summarize(events: list[str], complete: Callable[[str, str], str]) -> str:
    """A one-sentence summary, or an empty string when nothing has happened yet."""
    if not events:
        return ""
    return complete(summary_model(), build_prompt(events)).strip()
