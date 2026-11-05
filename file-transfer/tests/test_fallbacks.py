import unittest
import urllib.error

from transfer.notifications import Owner, notify_owner, recipient_for
from transfer.regions import DEFAULT_REGION, resolve_region
from transfer.webhooks import deliver_event


class Delivered:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class WebhookTests(unittest.TestCase):
    def test_transient_failure_is_retried(self):
        calls = []

        def opener(request, timeout):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.URLError("boom")
            return Delivered()

        result = deliver_event("https://example.test/hook", {"a": 1}, opener, lambda _: None)
        self.assertTrue(result.delivered)
        self.assertEqual(result.attempts, 2)


class RegionTests(unittest.TestCase):
    def test_unknown_region_uses_default(self):
        self.assertEqual(resolve_region("mars-1"), DEFAULT_REGION)


class NotificationTests(unittest.TestCase):
    def test_account_email_is_the_fallback(self):
        owner = Owner("o1", "account@example.test")
        self.assertEqual(recipient_for(owner), "account@example.test")

    def test_contact_email_wins(self):
        sent = []
        owner = Owner("o1", "account@example.test", "contact@example.test")
        notify_owner(owner, "Done", lambda to, subject: sent.append(to))
        self.assertEqual(sent, ["contact@example.test"])


if __name__ == "__main__":
    unittest.main()
