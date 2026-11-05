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


def notify_owner(owner: Owner, subject: str, send: Callable[[str, str], None]) -> bool:
    """Email an owner about one of their transfers."""
    if not owner.contact_email:
        return False
    send(owner.contact_email, subject)
    logger.info("Notified owner %s: %s", owner.id, subject)
    return True
