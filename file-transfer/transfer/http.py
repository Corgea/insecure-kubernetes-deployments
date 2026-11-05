"""Minimal request and response types used by the transfer handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional


class Headers(dict):
    """Case-insensitive header lookup."""

    def __init__(self, values: Optional[dict] = None):
        super().__init__()
        for key, value in (values or {}).items():
            self[key] = value

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key.lower(), value)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return super().get(key.lower(), default)


@dataclass
class UploadedFile:
    """One file part of a multipart request."""

    name: Optional[str]
    content: bytes


@dataclass
class Request:
    method: str
    path: str
    headers: Headers = field(default_factory=Headers)
    body: bytes = b""
    files: dict[str, UploadedFile] = field(default_factory=dict)


@dataclass
class Response:
    status: int
    payload: dict


def parse_multipart_files(parts: Iterable[dict]) -> dict[str, UploadedFile]:
    """Turn parsed multipart parts into uploaded files.

    A part without a file name is a plain form field and not a file, so it never
    reaches ``Request.files``.
    """
    files: dict[str, UploadedFile] = {}
    for part in parts:
        file_name = part.get("filename")
        if not file_name:
            continue
        files[part["name"]] = UploadedFile(
            name=file_name, content=part.get("content", b"")
        )
    return files
