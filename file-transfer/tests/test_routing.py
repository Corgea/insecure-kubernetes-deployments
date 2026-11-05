import tempfile
import unittest

from transfer.http import Headers, Request, UploadedFile
from transfer.service import Dependencies, handle_multipart_upload, route_request


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deps = Dependencies(root=self.tmp.name)
        created = handle_multipart_upload(
            Request(
                "POST",
                "/upload",
                Headers({"X-Owner": "alice"}),
                files={"file": UploadedFile("a.pdf", b"x")},
            ),
            self.deps,
        )
        self.transfer_id = created.payload["transfer"]["id"]

    def test_rename_without_a_new_name_is_a_400(self):
        response = route_request(
            Request("PATCH", "/rename", Headers({"X-Owner": "alice"})),
            "rename",
            self.transfer_id,
            self.deps,
        )
        self.assertEqual(response.status, 400)
        self.assertIn("X-New-Name", response.payload["message"])

    def test_rename_sets_the_display_name(self):
        response = route_request(
            Request("PATCH", "/rename", Headers({"X-Owner": "alice", "X-New-Name": "Q3 report"})),
            "rename",
            self.transfer_id,
            self.deps,
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(self.deps.transfers.get(self.transfer_id).display_name, "Q3 report")


if __name__ == "__main__":
    unittest.main()
