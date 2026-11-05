"""What one retention sweep did."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class SweepReport:
    started_at: float
    purged: list[str] = field(default_factory=list)
    warned: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    held: int = 0
    bytes_freed: int = 0
    bytes_by_owner: Counter = field(default_factory=Counter)

    def add_purged(self, transfer_id: str, owner: str, size: int) -> None:
        self.purged.append(transfer_id)
        self.bytes_freed += size
        self.bytes_by_owner[owner] += size

    @property
    def examined(self) -> int:
        return len(self.purged) + len(self.warned) + len(self.failed) + self.held

    def failure_rate(self) -> float:
        """Share of removal attempts that failed."""
        return len(self.failed) / (len(self.purged) + len(self.failed))

    def top_owners(self, count: int = 5) -> list[tuple[str, int]]:
        """The owners who got the most space back."""
        return self.bytes_by_owner.most_common(count)

    def summary(self) -> str:
        return (
            f"purged {len(self.purged)} ({human_bytes(self.bytes_freed)}), "
            f"warned {len(self.warned)}, failed {len(self.failed)}, held {self.held}"
        )

    def to_csv(self) -> str:
        """One row per owner, for the storage dashboard."""
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["owner", "bytes_freed"])
        for owner, size in self.bytes_by_owner.items():
            writer.writerow([owner, size])
        return out.getvalue()


def human_bytes(size: int) -> str:
    """A byte count for people to read."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
