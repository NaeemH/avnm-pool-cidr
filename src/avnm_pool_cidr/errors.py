"""Typed exceptions raised by avnm-pool-cidr."""

from __future__ import annotations


class AvnmPoolCidrError(Exception):
    """Base class for all avnm-pool-cidr errors."""


class AzCliNotFoundError(AvnmPoolCidrError):
    """Raised when the `az` CLI is not on PATH."""


class AzCliInvocationError(AvnmPoolCidrError):
    """Raised when an `az` invocation exits non-zero or returns unparseable JSON."""


class PoolNotFoundError(AvnmPoolCidrError):
    """Raised when the named IPAM pool cannot be located in the target VNM."""


class NoFreePrefixError(AvnmPoolCidrError):
    """Raised when no free prefix of the requested size exists in the pool."""


class InvalidPrefixSizeError(AvnmPoolCidrError):
    """Raised when the requested prefix size is incompatible with the pool address space."""
