import unittest
import urllib.error

from transfer.http import Headers, Request
from transfer.notifications import Owner, notify_owner
from transfer.regions import DEFAULT_REGION, UnknownRegion, resolve_region
from transfer.service import Dependencies, handle_create_transfer
from transfer.webhooks import deliver_event


class WebhookTests(unittest.TestCase):
    def test_failed_delivery_is_not_retried(self):
        calls = []

        def opener(request, timeout):
            calls.append(request)
            raise urllib.error.URLError("boom")

        result = deliver_event("https://example.test/hook", {"a": 1}, opener)
        self.assertFalse(result.delivered)
        self.assertEqual(len(calls), 1)


class RegionTests(unittest.TestCase):
    def test_no_region_uses_default(self):
        self.assertEqual(resolve_region(None), DEFAULT_REGION)

    def test_unknown_region_is_an_error(self):
        with self.assertRaises(UnknownRegion):
            resolve_region("mars-1")

    def test_create_rejects_unknown_region(self):
        request = Request(
            "POST",
            "/transfers",
            Headers({"X-Owner": "alice", "Upload-Length": "3", "Upload-Region": "mars-1"}),
        )
        response = handle_create_transfer(request, Dependencies(root="/nonexistent"))
        self.assertEqual(response.status, 400)


class NotificationTests(unittest.TestCase):
    def test_no_contact_address_drops_the_notification(self):
        sent = []
        owner = Owner("o1", "account@example.test")
        self.assertFalse(notify_owner(owner, "Done", lambda to, subject: sent.append(to)))
        self.assertEqual(sent, [])

    def test_contact_address_is_used(self):
        sent = []
        owner = Owner("o1", "account@example.test", "contact@example.test")
        self.assertTrue(notify_owner(owner, "Done", lambda to, subject: sent.append(to)))
        self.assertEqual(sent, ["contact@example.test"])


if __name__ == "__main__":
    unittest.main()
