"""One-time share codes for finished transfers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading

HEX_DIGITS = frozenset("0123456789abcdef")
CODE_BYTES = 8  # Eight bytes print as sixteen hex digits.
GROUP_SIZE = 4


def new_code() -> str:
    """A new random share code."""
    return secrets.token_hex(CODE_BYTES)


def format_code(code: str) -> str:
    """Group a code for display: ``ab12-cd34-ef56-7890``."""
    return "-".join(code[i : i + GROUP_SIZE] for i in range(0, len(code), GROUP_SIZE))


def normalize_code(raw: str) -> str:
    """Canonical form of a typed code: lower case, with everything else removed."""
    return "".join(ch for ch in raw.lower() if ch in HEX_DIGITS)


def has_capacity(used: int, size: int, limit: int) -> bool:
    """True when a share of this size still fits, including an exact fit."""
    return limit >= used + size


def _digest(owner: str, code: str) -> str:
    return hashlib.sha256(f"{owner}:{code}".encode("utf-8")).hexdigest()


class ShareCodeStore:
    """Issued codes, kept only as digests."""

    def __init__(self):
        self._lock = threading.Lock()
        self._digests: dict[str, list[str]] = {}

    def issue(self, owner: str) -> str:
        """Create a code for an owner and return it for display."""
        code = new_code()
        with self._lock:
            self._digests.setdefault(owner, []).append(_digest(owner, code))
        return format_code(code)

    def redeem(self, owner: str, raw: str) -> bool:
        """Use a code. A code works once, however it was typed."""
        candidate = _digest(owner, normalize_code(raw))
        with self._lock:
            digests = self._digests.get(owner, [])
            for digest in digests:
                if hmac.compare_digest(digest, candidate):
                    digests.remove(digest)
                    return True
        return False
