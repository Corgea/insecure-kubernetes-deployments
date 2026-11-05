"""How long finished transfers are kept."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from ..service import FILE_TYPES, Transfer

DAY_SECONDS = 24 * 60 * 60
LEGAL_HOLD_TAG = "legal-hold"


@dataclass(frozen=True)
class RetentionRule:
    name: str
    keep_days: int
    warn_days: int = 3


RULES = {
    "video": RetentionRule("video", 14),
    "image": RetentionRule("image", 30),
    "text": RetentionRule("text", 90, warn_days=7),
    "application": RetentionRule("application", 60),
}
DEFAULT_RULE = RetentionRule("default", 30)


def category_for(file_path: Optional[str]) -> str:
    """The retention category of a stored file."""
    extension = os.path.splitext(file_path)[1].lstrip(".").lower()
    file_type = FILE_TYPES.get(extension)
    return file_type.category if file_type else "other"


def rule_for(transfer: Transfer) -> RetentionRule:
    """The retention rule that applies to a transfer."""
    return RULES.get(category_for(transfer.final_path), DEFAULT_RULE)


def expires_at(transfer: Transfer, rule: RetentionRule) -> float:
    """When a finished transfer stops being kept."""
    return transfer.completed_at + rule.keep_days * DAY_SECONDS


def warn_at(transfer: Transfer, rule: RetentionRule) -> float:
    """When the owner hears that a transfer is about to go."""
    return expires_at(transfer, rule) - rule.warn_days * DAY_SECONDS
