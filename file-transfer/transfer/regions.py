"""Storage regions a transfer can be placed in."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

REGIONS = frozenset({"us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-south-1"})
DEFAULT_REGION = "us-east-1"


def resolve_region(requested: Optional[str]) -> str:
    """The region to store a transfer in, falling back to the default."""
    if requested in REGIONS:
        return requested
    logger.info("Unknown region %r, using %s", requested, DEFAULT_REGION)
    return DEFAULT_REGION


def storage_prefix(owner: str, requested_region: Optional[str]) -> str:
    """Where an owner's files live for the requested region."""
    return f"{resolve_region(requested_region)}/{owner}/"
