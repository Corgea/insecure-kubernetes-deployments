"""Monthly storage usage summary for owners."""

from __future__ import annotations

import datetime
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

MEGABYTE = 1024 * 1024


def month_start(now=None):
    """Midnight on the first day of the current month."""
    now = now or datetime.datetime.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def owner_key(owner: str) -> str:
    """Owners are grouped without regard to case."""
    return owner.strip().lower()


def percent_used(used: int, limit: int) -> float:
    """Share of the quota in use, for display."""
    return round(used / limit * 100, 1)


def average_size(sizes: list[int]) -> int:
    """Average transfer size in whole bytes."""
    return int(sum(sizes) / len(sizes)) if sizes else 0


def usage_by_owner(transfers: list, since: datetime.datetime) -> dict[str, list[int]]:
    """Sizes of the transfers each owner finished since a point in time."""
    usage = defaultdict(list)
    for transfer in transfers:
        finished = datetime.datetime.fromtimestamp(transfer.completed_at)
        if finished >= since:
            usage[owner_key(transfer.owner)].append(transfer.length)
    return usage


def render_line(owner: str, sizes: list[int], limit: int) -> str:
    """One owner's line in the summary."""
    used = sum(sizes)
    return (
        f"{owner}: {len(sizes)} transfers, {used / MEGABYTE:.2f} MB "
        f"({percent_used(used, limit)}% of quota), "
        f"average {average_size(sizes) / MEGABYTE:.2f} MB"
    )


def render_summary(transfers: list, limit: int, now=None) -> str:
    """The text of the monthly summary, largest users first."""
    usage = usage_by_owner(transfers, month_start(now))
    logger.info("Building usage summary for %s owners: %s", len(usage), list(usage))
    ordered = sorted(usage.items(), key=lambda pair: sum(pair[1]), reverse=True)
    return "\n".join(render_line(owner, sizes, limit) for owner, sizes in ordered)
