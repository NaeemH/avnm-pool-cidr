"""Pure-Python CIDR computations using only the stdlib `ipaddress` module.

These helpers know nothing about Azure -- they take a parent address space and a
list of already-allocated child prefixes, and return the next free prefix of a
given size, or enumerate utilization. Splitting this out makes the math trivial
to unit-test without touching `az`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_network

from avnm_pool_cidr.errors import InvalidPrefixSizeError, NoFreePrefixError

IPNetwork = IPv4Network | IPv6Network


@dataclass(frozen=True)
class Utilization:
    """Summary of how much of a parent prefix is already allocated."""

    parent: IPNetwork
    allocated: tuple[IPNetwork, ...]
    total_addresses: int
    allocated_addresses: int

    @property
    def free_addresses(self) -> int:
        return self.total_addresses - self.allocated_addresses

    @property
    def percent_used(self) -> float:
        if self.total_addresses == 0:
            return 0.0
        return (self.allocated_addresses / self.total_addresses) * 100.0


def parse_network(value: str) -> IPNetwork:
    """Parse a CIDR string into an IPv4/IPv6 Network. Strict (no host bits)."""
    return ip_network(value, strict=True)


def _iter_candidates(parent: IPNetwork, new_prefix: int) -> Iterator[IPNetwork]:
    """Yield every subnet of `parent` at exactly `new_prefix` length, in order."""
    if new_prefix < parent.prefixlen or new_prefix > parent.max_prefixlen:
        raise InvalidPrefixSizeError(
            f"Requested prefix /{new_prefix} is not inside parent {parent} "
            f"(parent is /{parent.prefixlen}, max is /{parent.max_prefixlen})"
        )
    yield from parent.subnets(new_prefix=new_prefix)


def next_free_prefix(
    parent: IPNetwork,
    allocated: Iterable[IPNetwork],
    new_prefix: int,
) -> IPNetwork:
    """Return the first subnet of `parent` at `/new_prefix` that does not overlap any
    of the already-`allocated` networks.

    Raises:
        InvalidPrefixSizeError: if `new_prefix` is out of range for `parent`.
        NoFreePrefixError: if every candidate overlaps an allocated network.
    """
    allocated_list = list(allocated)
    for candidate in _iter_candidates(parent, new_prefix):
        if not any(candidate.overlaps(a) for a in allocated_list):
            return candidate
    raise NoFreePrefixError(
        f"No free /{new_prefix} subnet available in {parent} "
        f"({len(allocated_list)} allocations already in pool)"
    )


def utilization(parent: IPNetwork, allocated: Iterable[IPNetwork]) -> Utilization:
    """Compute address-level utilization for a parent prefix.

    Overlapping allocated networks are NOT double-counted; their union is used.
    """
    allocated_tuple = tuple(allocated)
    if not allocated_tuple:
        return Utilization(
            parent=parent,
            allocated=(),
            total_addresses=parent.num_addresses,
            allocated_addresses=0,
        )
    # collapse_addresses requires homogeneous network versions; branch on the
    # parent's version (IPAM pools never mix v4 and v6 in a single pool).
    from ipaddress import collapse_addresses

    merged: tuple[IPNetwork, ...]
    if isinstance(parent, IPv4Network):
        v4 = [n for n in allocated_tuple if isinstance(n, IPv4Network)]
        merged = tuple(collapse_addresses(v4))
    else:
        v6 = [n for n in allocated_tuple if isinstance(n, IPv6Network)]
        merged = tuple(collapse_addresses(v6))
    allocated_addresses = sum(n.num_addresses for n in merged)
    return Utilization(
        parent=parent,
        allocated=merged,
        total_addresses=parent.num_addresses,
        allocated_addresses=allocated_addresses,
    )
