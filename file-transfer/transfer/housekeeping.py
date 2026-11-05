"""Nightly housekeeping: remove finished transfers past their retention."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from .service import ChunkManager, Dependencies, Transfer

logger = logging.getLogger(__name__)

RETENTION_SECONDS = 30 * 24 * 60 * 60
LEGAL_HOLD_TAG = "legal-hold"


def is_expired(transfer: Transfer, now: float) -> bool:
    """True once a finished transfer has outlived its retention."""
    if transfer.completed_at is None:
        return False
    return now - transfer.completed_at > RETENTION_SECONDS


def purge_expired(
    deps: Dependencies, now: Optional[float] = None, dry_run: bool = False
) -> list[str]:
    """Delete finished transfers past retention and return their ids.

    Transfers on legal hold are kept, and the skip is recorded. A file that
    cannot be removed is logged and audited, and the sweep moves on.
    """
    now = time.time() if now is None else now
    purged = []
    for transfer in deps.transfers.finished():
        if LEGAL_HOLD_TAG in transfer.tags:
            deps.audit.record(transfer.id, "purge_skipped", reason="legal hold")
            continue
        if not is_expired(transfer, now):
            continue
        if dry_run:
            purged.append(transfer.id)
            continue
        try:
            if transfer.final_path:
                os.remove(transfer.final_path)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", transfer.final_path, exc)
            deps.audit.record(transfer.id, "purge_failed", error=str(exc))
            continue
        deps.quotas.release(transfer.owner, transfer.length)
        ChunkManager(deps.root, transfer.id).discard()
        deps.transfers.delete(transfer.id)
        deps.audit.record(transfer.id, "purged")
        purged.append(transfer.id)
    return purged
