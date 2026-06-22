"""Unit tests for the pure CIDR computation layer."""

from __future__ import annotations

from ipaddress import ip_network

import pytest

from avnm_pool_cidr.cidr import next_free_prefix, parse_network, utilization
from avnm_pool_cidr.errors import InvalidPrefixSizeError, NoFreePrefixError


class TestParseNetwork:
    def test_parses_ipv4(self) -> None:
        n = parse_network("10.0.0.0/16")
        assert str(n) == "10.0.0.0/16"

    def test_parses_ipv6(self) -> None:
        n = parse_network("fd00::/48")
        assert str(n) == "fd00::/48"

    def test_strict_mode_rejects_host_bits(self) -> None:
        with pytest.raises(ValueError):
            parse_network("10.0.0.1/24")


class TestNextFreePrefix:
    def test_first_call_on_empty_pool_returns_lowest_subnet(self) -> None:
        parent = ip_network("10.0.0.0/16")
        result = next_free_prefix(parent, [], 24)
        assert result == ip_network("10.0.0.0/24")

    def test_skips_overlapping_allocations(self) -> None:
        parent = ip_network("10.0.0.0/16")
        allocated = [ip_network("10.0.0.0/24"), ip_network("10.0.1.0/24")]
        result = next_free_prefix(parent, allocated, 24)
        assert result == ip_network("10.0.2.0/24")

    def test_skips_partial_overlap_with_larger_existing(self) -> None:
        # An existing /22 occupies 10.0.0.0/22; a new /24 must land >= 10.0.4.0
        parent = ip_network("10.0.0.0/16")
        allocated = [ip_network("10.0.0.0/22")]
        result = next_free_prefix(parent, allocated, 24)
        assert result == ip_network("10.0.4.0/24")

    def test_skips_when_existing_is_smaller_subnet_inside(self) -> None:
        # An existing /26 occupies part of a /24 -- the whole /24 is unavailable
        parent = ip_network("10.0.0.0/16")
        allocated = [ip_network("10.0.0.0/26")]
        result = next_free_prefix(parent, allocated, 24)
        assert result == ip_network("10.0.1.0/24")

    def test_raises_when_pool_full(self) -> None:
        parent = ip_network("10.0.0.0/24")
        allocated = [ip_network("10.0.0.0/24")]
        with pytest.raises(NoFreePrefixError):
            next_free_prefix(parent, allocated, 24)

    def test_raises_on_prefix_larger_than_parent(self) -> None:
        parent = ip_network("10.0.0.0/24")
        with pytest.raises(InvalidPrefixSizeError):
            next_free_prefix(parent, [], 16)

    def test_raises_on_prefix_out_of_range(self) -> None:
        parent = ip_network("10.0.0.0/24")
        with pytest.raises(InvalidPrefixSizeError):
            next_free_prefix(parent, [], 33)

    def test_equal_prefix_returns_parent_when_unallocated(self) -> None:
        parent = ip_network("10.0.0.0/24")
        result = next_free_prefix(parent, [], 24)
        assert result == parent

    def test_ipv6(self) -> None:
        parent = ip_network("fd00::/48")
        allocated = [ip_network("fd00::/64")]
        result = next_free_prefix(parent, allocated, 64)
        assert result == ip_network("fd00:0:0:1::/64")


class TestUtilization:
    def test_empty_pool_is_zero_percent(self) -> None:
        parent = ip_network("10.0.0.0/16")
        u = utilization(parent, [])
        assert u.total_addresses == 65536
        assert u.allocated_addresses == 0
        assert u.percent_used == 0.0

    def test_single_allocation(self) -> None:
        parent = ip_network("10.0.0.0/16")
        u = utilization(parent, [ip_network("10.0.0.0/24")])
        assert u.allocated_addresses == 256
        assert u.free_addresses == 65280
        assert u.percent_used == pytest.approx(256 / 65536 * 100)

    def test_overlapping_allocations_are_merged_not_double_counted(self) -> None:
        parent = ip_network("10.0.0.0/16")
        # /23 contains both /24s -- total should still be 512, not 1024
        u = utilization(
            parent,
            [
                ip_network("10.0.0.0/23"),
                ip_network("10.0.0.0/24"),
                ip_network("10.0.1.0/24"),
            ],
        )
        assert u.allocated_addresses == 512

    def test_adjacent_allocations_get_collapsed(self) -> None:
        parent = ip_network("10.0.0.0/16")
        u = utilization(
            parent,
            [ip_network("10.0.0.0/24"), ip_network("10.0.1.0/24")],
        )
        assert u.allocated_addresses == 512
        assert len(u.allocated) == 1  # collapsed to a single /23

    def test_fully_allocated_pool(self) -> None:
        parent = ip_network("10.0.0.0/24")
        u = utilization(parent, [parent])
        assert u.percent_used == 100.0
        assert u.free_addresses == 0
