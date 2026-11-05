import tempfile
import unittest

from transfer.http import Headers, Request, UploadedFile
from transfer.service import (
    Dependencies,
    FileManager,
    handle_chunk_patch,
    handle_create_transfer,
    handle_multipart_upload,
)


class UploadNameErrorTests(unittest.TestCase):
    def test_accepted_name(self):
        self.assertIsNone(FileManager.upload_name_error("report.pdf"))

    def test_unknown_extension(self):
        self.assertIn("file type", FileManager.upload_name_error("report.notareal"))

    def test_folder_in_name(self):
        self.assertIn("folder", FileManager.upload_name_error("../report.pdf"))


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deps = Dependencies(root=self.tmp.name)

    def test_multipart_rejects_bad_extension(self):
        request = Request(
            "POST",
            "/upload",
            Headers({"X-Owner": "alice"}),
            files={"file": UploadedFile("report.notareal", b"x")},
        )
        self.assertEqual(handle_multipart_upload(request, self.deps).status, 400)
        self.assertEqual(self.deps.quotas.used("alice"), 0)

    def test_chunk_rejects_folder_in_name(self):
        created = handle_create_transfer(
            Request("POST", "/transfers", Headers({"X-Owner": "alice", "Upload-Length": "3"})),
            self.deps,
        )
        request = Request(
            "PATCH",
            "/transfers",
            Headers(
                {
                    "X-Owner": "alice",
                    "Upload-Offset": "0",
                    "Upload-Length": "3",
                    "Upload-Name": "../report.pdf",
                }
            ),
            body=b"abc",
        )
        response = handle_chunk_patch(request, created.payload["transfer"]["id"], self.deps)
        self.assertEqual(response.status, 400)
        self.assertEqual(self.deps.quotas.used("alice"), 0)


if __name__ == "__main__":
    unittest.main()
