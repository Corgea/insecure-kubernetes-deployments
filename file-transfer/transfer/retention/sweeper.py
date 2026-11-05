"""Remove finished transfers once their retention runs out."""

from __future__ import annotations

import logging
import os
import time
from typing import Callable

from ..service import ChunkManager, Dependencies, Transfer
from .policy import LEGAL_HOLD_TAG, RetentionRule, expires_at, rule_for, warn_at
from .report import SweepReport

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 200


class RetentionSweeper:
    """One instance runs per night."""

    def __init__(
        self,
        deps: Dependencies,
        send_warning: Callable[[str, str], None],
        clock: Callable[[], float] = time.time,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.deps = deps
        self.send_warning = send_warning
        self.clock = clock
        self.batch_size = batch_size
        self._warned: set[str] = set()

    def sweep(self) -> SweepReport:
        """Warn about transfers that are nearly due and remove those that are due."""
        now = self.clock()
        report = SweepReport(started_at=now)
        for transfer in self.deps.transfers.finished()[: self.batch_size]:
            if LEGAL_HOLD_TAG in transfer.tags:
                report.held += 1
                continue
            rule = rule_for(transfer)
            if now >= expires_at(transfer, rule):
                self._expire(transfer, rule, report)
            elif now >= warn_at(transfer, rule):
                self._warn(transfer, rule, report)
        logger.info("Retention sweep: %s", report.summary())
        return report

    def _expire(
        self, transfer: Transfer, rule: RetentionRule, report: SweepReport
    ) -> None:
        try:
            os.remove(transfer.final_path)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", transfer.final_path, exc)
            report.failed.append(transfer.id)
            return
        self.deps.quotas.release(transfer.owner, transfer.length)
        ChunkManager(self.deps.root, transfer.id).discard()
        self.deps.transfers.delete(transfer.id)
        self.deps.audit.record(transfer.id, "purged", rule=rule.name)
        report.add_purged(transfer.id, transfer.owner, transfer.length)

    def _warn(
        self, transfer: Transfer, rule: RetentionRule, report: SweepReport
    ) -> None:
        if transfer.id in self._warned:
            return
        self.send_warning(
            transfer.owner,
            f"Transfer {transfer.id} will be removed in {rule.warn_days} days.",
        )
        self._warned.add(transfer.id)
        report.warned.append(transfer.id)
