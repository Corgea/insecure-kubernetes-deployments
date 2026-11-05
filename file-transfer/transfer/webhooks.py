"""Outbound webhooks for transfer events."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 10
MAX_DELIVERY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    attempts: int
    status: Optional[int] = None
    error: Optional[str] = None


def deliver_event(
    endpoint: str,
    event: dict,
    opener: Callable = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> DeliveryResult:
    """POST an event to an owner's endpoint, retrying transient failures."""
    body = json.dumps(event, sort_keys=True).encode("utf-8")
    last_error = None
    for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with opener(request, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
                return DeliveryResult(
                    delivered=True, attempts=attempt, status=response.status
                )
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
            logger.warning("Delivery attempt %s failed: %s", attempt, exc)
            if attempt < MAX_DELIVERY_ATTEMPTS:
                sleep(RETRY_BACKOFF_SECONDS * attempt)
    return DeliveryResult(
        delivered=False, attempts=MAX_DELIVERY_ATTEMPTS, error=last_error
    )


def publish_transfer_completed(transfer, endpoints: dict) -> bool:
    """Tell an owner's endpoint that a transfer finished."""
    endpoint = endpoints.get(transfer.owner)
    if endpoint is None:
        return False
    event = {"type": "transfer.completed", "transfer_id": transfer.id}
    return deliver_event(endpoint, event).delivered
