import unittest

from transfer.share_codes import ShareCodeStore, format_code, has_capacity, normalize_code


class ShareCodeTests(unittest.TestCase):
    def test_normalize_keeps_only_hex(self):
        self.assertEqual(normalize_code("AB12-cd34"), "ab12cd34")

    def test_format_groups_digits(self):
        self.assertEqual(format_code("ab12cd34"), "ab12-cd34")

    def test_exact_fit_has_capacity(self):
        self.assertTrue(has_capacity(4, 6, 10))
        self.assertFalse(has_capacity(5, 6, 10))

    def test_code_works_once(self):
        store = ShareCodeStore()
        code = store.issue("alice")
        self.assertTrue(store.redeem("alice", code.upper()))
        self.assertFalse(store.redeem("alice", code))


if __name__ == "__main__":
    unittest.main()
