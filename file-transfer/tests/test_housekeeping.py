import os
import tempfile
import time
import unittest

from transfer.housekeeping import purge_expired
from transfer.retention.policy import DAY_SECONDS
from transfer.service import Dependencies


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deps = Dependencies(root=self.tmp.name)
        self.warnings = []

    def finished(self, age_days):
        transfer = self.deps.transfers.create("alice", 3)
        path = os.path.join(self.tmp.name, f"{transfer.id}.png")
        with open(path, "wb") as handle:
            handle.write(b"abc")
        transfer.final_path = path
        transfer.state = "complete"
        transfer.completed_at = time.time() - age_days * DAY_SECONDS
        self.deps.quotas.reserve("alice", 3)
        return transfer

    def sweep(self):
        return purge_expired(self.deps, lambda owner, text: self.warnings.append(text))

    def test_due_transfer_is_purged_and_fresh_one_kept(self):
        old = self.finished(31)
        fresh = self.finished(1)
        report = self.sweep()
        self.assertEqual(report.purged, [old.id])
        self.assertIsNotNone(self.deps.transfers.get(fresh.id))
        self.assertEqual(self.deps.quotas.used("alice"), 3)

    def test_nearly_due_transfer_warns_the_owner(self):
        nearly = self.finished(28)
        report = self.sweep()
        self.assertEqual(report.warned, [nearly.id])
        self.assertEqual(len(self.warnings), 1)

    def test_legal_hold_is_kept(self):
        held = self.finished(31)
        held.tags = frozenset({"legal-hold"})
        report = self.sweep()
        self.assertEqual(report.held, 1)
        self.assertIsNotNone(self.deps.transfers.get(held.id))


if __name__ == "__main__":
    unittest.main()
