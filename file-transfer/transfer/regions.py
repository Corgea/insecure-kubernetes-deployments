"""Storage regions a transfer can be placed in."""

from __future__ import annotations

from typing import Optional

REGIONS = frozenset({"us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-south-1"})
DEFAULT_REGION = "us-east-1"


class UnknownRegion(ValueError):
    """A client named a storage region the service does not have."""


def resolve_region(requested: Optional[str]) -> str:
    """The region to store a transfer in.

    A client that names no region gets the default. A client that names an unknown
    region gets an error, never the default: storing the file somewhere it did not
    ask for would break data residency commitments.
    """
    if requested is None:
        return DEFAULT_REGION
    if requested in REGIONS:
        return requested
    raise UnknownRegion(requested)


def storage_prefix(owner: str, requested_region: Optional[str]) -> str:
    """Where an owner's files live for the requested region."""
    return f"{resolve_region(requested_region)}/{owner}/"
