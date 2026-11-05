import unittest

from tests.browser.fake_page import FakePage
from tests.browser.pages import DownloadPage

UNKNOWN_EMAIL = "nobody@example.test"
GENERIC_MESSAGE = "If that address has a transfer, we sent a new code."


class NewCodeTests(unittest.TestCase):
    def setUp(self):
        self.page = FakePage()
        self.download = DownloadPage(self.page)
        self.download.open()

    def test_unknown_address_gets_the_generic_message(self):
        self.download.submit_email(UNKNOWN_EMAIL)
        self.download.request_new_code(UNKNOWN_EMAIL)
        self.assertEqual(self.download.message(), GENERIC_MESSAGE)


if __name__ == "__main__":
    unittest.main()
