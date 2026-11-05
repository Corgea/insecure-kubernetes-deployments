"""Emails sent to transfer owners."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Owner:
    id: str
    account_email: str
    contact_email: Optional[str] = None


def recipient_for(owner: Owner) -> str:
    """The address to notify, falling back to the account email."""
    return owner.contact_email or owner.account_email


def notify_owner(owner: Owner, subject: str, send: Callable[[str, str], None]) -> bool:
    """Email an owner about one of their transfers."""
    send(recipient_for(owner), subject)
    logger.info("Notified owner %s: %s", owner.id, subject)
    return True
