"""Outbound webhooks for transfer events."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    status: Optional[int] = None
    error: Optional[str] = None


def deliver_event(
    endpoint: str,
    event: dict,
    opener: Callable = urllib.request.urlopen,
) -> DeliveryResult:
    """POST an event to an owner's endpoint exactly once.

    Deliveries are never retried. Receivers are not idempotent, so a retry after
    a timeout can apply the same event twice. A failed delivery goes back to the
    caller, which puts it on the operator replay queue.
    """
    body = json.dumps(event, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
            return DeliveryResult(delivered=True, status=response.status)
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Delivery failed: %s", exc)
        return DeliveryResult(delivered=False, error=str(exc))


def publish_transfer_completed(transfer, endpoints: dict, replay_queue: list) -> bool:
    """Tell an owner's endpoint that a transfer finished."""
    endpoint = endpoints.get(transfer.owner)
    if endpoint is None:
        return False
    event = {"type": "transfer.completed", "transfer_id": transfer.id}
    result = deliver_event(endpoint, event)
    if not result.delivered:
        replay_queue.append(event)
    return result.delivered
