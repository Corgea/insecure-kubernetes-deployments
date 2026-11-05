import datetime
import unittest
from types import SimpleNamespace

from transfer.usage_summary import average_size, month_start, owner_key, render_summary


class UsageSummaryTests(unittest.TestCase):
    def test_month_start(self):
        now = datetime.datetime(2026, 3, 14, 9, 30)
        self.assertEqual(month_start(now), datetime.datetime(2026, 3, 1))

    def test_owner_key_ignores_case(self):
        self.assertEqual(owner_key(" Alice "), "alice")

    def test_average_of_nothing_is_zero(self):
        self.assertEqual(average_size([]), 0)

    def test_largest_user_first(self):
        now = datetime.datetime(2026, 3, 14)
        stamp = datetime.datetime(2026, 3, 2).timestamp()
        transfers = [
            SimpleNamespace(owner="alice", length=1024, completed_at=stamp),
            SimpleNamespace(owner="bob", length=2048, completed_at=stamp),
        ]
        lines = render_summary(transfers, 1024 * 1024, now).splitlines()
        self.assertTrue(lines[0].startswith("bob"))


if __name__ == "__main__":
    unittest.main()
