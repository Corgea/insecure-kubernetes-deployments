import os
import tempfile
import time
import unittest

from transfer.housekeeping import RETENTION_SECONDS, purge_expired
from transfer.service import Dependencies


class PurgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deps = Dependencies(root=self.tmp.name)

    def finished(self, age):
        transfer = self.deps.transfers.create("alice", 3)
        path = os.path.join(self.tmp.name, f"{transfer.id}.pdf")
        with open(path, "wb") as handle:
            handle.write(b"abc")
        transfer.final_path = path
        transfer.state = "complete"
        transfer.completed_at = time.time() - age
        self.deps.quotas.reserve("alice", 3)
        return transfer

    def test_old_transfers_are_purged(self):
        old = self.finished(RETENTION_SECONDS + 60)
        fresh = self.finished(60)
        self.assertEqual(purge_expired(self.deps), [old.id])
        self.assertIsNotNone(self.deps.transfers.get(fresh.id))

    def test_legal_hold_is_kept(self):
        held = self.finished(RETENTION_SECONDS + 60)
        held.tags = frozenset({"legal-hold"})
        self.assertEqual(purge_expired(self.deps), [])

    def test_dry_run_changes_nothing(self):
        old = self.finished(RETENTION_SECONDS + 60)
        self.assertEqual(purge_expired(self.deps, dry_run=True), [old.id])
        self.assertIsNotNone(self.deps.transfers.get(old.id))


if __name__ == "__main__":
    unittest.main()
