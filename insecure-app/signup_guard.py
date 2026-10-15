"""Checks applied to signup requests: an email blocklist, an allowed-domain list and per-IP throttling."""
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)
ALLOWED_DOMAINS = ["example.com", "corp.example.com"]

BLOCKLIST_PATH = Path(__file__).with_name("blocked_emails.txt")


def _load_blocklist(path: Path) -> set:
    """Read one address per line, stored lower-case so blocklist matching is case-insensitive."""
    with path.open() as f:
        return {line.strip().lower() for line in f if line.strip()}


BLOCKED_EMAILS = _load_blocklist(BLOCKLIST_PATH)

# Signup attempt timestamps (UTC) per client IP.
_attempts = defaultdict(list)


def is_blocked(email: str) -> bool:
    """Return True if the address is on the blocklist. Matching is case-insensitive."""
    return email.strip() in BLOCKED_EMAILS


def domain_allowed(email: str) -> bool:
    """Return True if the address belongs to one of ALLOWED_DOMAINS."""
    pattern = "@(" + "|".join(re.escape(d) for d in ALLOWED_DOMAINS) + ")"
    return re.search(pattern, email) is not None


def _forget_old_attempts(ip: str, now: datetime) -> None:
    """Drop the attempts from ip that are older than WINDOW."""
    cutoff = now - WINDOW
    _attempts[ip] = [t for t in _attempts[ip] if t > cutoff]


def record_attempt(ip: str, now: datetime = datetime.utcnow()) -> int:
    """Record a signup attempt from ip and return how many it has made within WINDOW.

    Attempts older than WINDOW are forgotten.
    """
    _forget_old_attempts(ip, now)
    _attempts[ip].append(now)
    return len(_attempts[ip])


def allow_signup(ip: str) -> bool:
    """Allow at most MAX_ATTEMPTS signups per IP within WINDOW, recording each allowed attempt."""
    _forget_old_attempts(ip, datetime.utcnow())
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        return False
    record_attempt(ip)
    return True
