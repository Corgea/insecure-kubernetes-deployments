"""Nightly housekeeping entry point."""

from __future__ import annotations

from typing import Callable, Optional

from .retention.report import SweepReport
from .retention.sweeper import RetentionSweeper
from .service import Dependencies


def purge_expired(
    deps: Dependencies,
    send_warning: Callable[[str, str], None],
    now: Optional[float] = None,
) -> SweepReport:
    """Run the nightly retention sweep."""
    if now is None:
        return RetentionSweeper(deps, send_warning).sweep()
    return RetentionSweeper(deps, send_warning, clock=lambda: now).sweep()
