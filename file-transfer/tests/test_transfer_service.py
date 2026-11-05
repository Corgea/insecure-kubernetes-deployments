import tempfile
import unittest

from transfer.http import Headers, Request, parse_multipart_files
from transfer.service import (
    Dependencies,
    FileManager,
    handle_cancel_transfer,
    handle_chunk_patch,
    handle_create_transfer,
    handle_multipart_upload,
)


def chunk_request(offset, length, name, body, owner="alice"):
    headers = {"X-Owner": owner, "Upload-Offset": str(offset), "Upload-Length": str(length)}
    if name is not None:
        headers["Upload-Name"] = name
    return Request("PATCH", "/transfers", Headers(headers), body=body)


class ChunkPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deps = Dependencies(root=self.tmp.name)
        created = handle_create_transfer(
            Request("POST", "/transfers", Headers({"X-Owner": "alice", "Upload-Length": "6"})),
            self.deps,
        )
        self.transfer_id = created.payload["transfer"]["id"]

    def test_missing_name_header_is_rejected_with_400(self):
        response = handle_chunk_patch(
            chunk_request(0, 6, None, b"abc"), self.transfer_id, self.deps
        )
        self.assertEqual(response.status, 400)
        self.assertIn("Upload-Name", response.payload["message"])

    def test_empty_name_header_is_rejected_with_400(self):
        response = handle_chunk_patch(
            chunk_request(0, 6, "", b"abc"), self.transfer_id, self.deps
        )
        self.assertEqual(response.status, 400)

    def test_chunks_combine_into_the_final_file(self):
        handle_chunk_patch(
            chunk_request(0, 6, "report.pdf", b"abc"), self.transfer_id, self.deps
        )
        done = handle_chunk_patch(
            chunk_request(3, 6, "report.pdf", b"def"), self.transfer_id, self.deps
        )
        self.assertEqual(done.payload["transfer"]["state"], "complete")
        transfer = self.deps.transfers.get(self.transfer_id)
        with open(transfer.final_path, "rb") as handle:
            self.assertEqual(handle.read(), b"abcdef")

    def test_another_owner_cannot_add_chunks(self):
        response = handle_chunk_patch(
            chunk_request(0, 6, "report.pdf", b"abc", owner="mallory"),
            self.transfer_id,
            self.deps,
        )
        self.assertEqual(response.status, 403)

    def test_cancel_gives_quota_back(self):
        handle_chunk_patch(
            chunk_request(0, 6, "report.pdf", b"abc"), self.transfer_id, self.deps
        )
        handle_cancel_transfer(self.transfer_id, self.deps)
        self.assertEqual(self.deps.quotas.used("alice"), 0)


class MultipartTests(unittest.TestCase):
    def test_parts_without_a_file_name_never_become_files(self):
        files = parse_multipart_files(
            [{"name": "file", "content": b"x"}, {"name": "file", "filename": "", "content": b"y"}]
        )
        self.assertEqual(files, {})

    def test_named_part_is_stored(self):
        with tempfile.TemporaryDirectory() as root:
            deps = Dependencies(root=root)
            files = parse_multipart_files(
                [{"name": "file", "filename": "report.pdf", "content": b"x"}]
            )
            response = handle_multipart_upload(
                Request("POST", "/upload", Headers({"X-Owner": "alice"}), files=files), deps
            )
            self.assertEqual(response.status, 200)


class FileManagerTests(unittest.TestCase):
    def test_extension_check(self):
        self.assertTrue(FileManager.validate_file_extension("a.PDF"))
        self.assertFalse(FileManager.validate_file_extension("a.notareal"))

    def test_safe_names(self):
        self.assertTrue(FileManager.is_safe_file_name("a.pdf"))
        self.assertFalse(FileManager.is_safe_file_name("../a.pdf"))


if __name__ == "__main__":
    unittest.main()
