"""Unit tests for the `az`-shelling IPAM layer (subprocess mocked)."""

from __future__ import annotations

import json
import subprocess
from ipaddress import ip_network
from typing import Any

import pytest
from pytest_mock import MockerFixture

from avnm_pool_cidr.errors import (
    AzCliInvocationError,
    AzCliNotFoundError,
    PoolNotFoundError,
)
from avnm_pool_cidr.ipam import (
    PoolRef,
    get_pool,
    list_associated_resources,
)

REF = PoolRef(
    subscription="sub-123",
    resource_group="rg-net",
    network_manager="vnm-prod",
    name="prod-pool",
)


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> Any:
    cp = subprocess.CompletedProcess[str](
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    return cp


class TestRequireAz:
    def test_raises_when_az_missing(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value=None)
        with pytest.raises(AzCliNotFoundError):
            get_pool(REF)


class TestGetPool:
    def test_returns_parsed_pool(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        payload = {
            "name": "prod-pool",
            "location": "eastus",
            "properties": {
                "addressPrefixes": ["10.0.0.0/16", "10.1.0.0/16"],
                "parentPoolName": None,
            },
        }
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stdout=json.dumps(payload)),
        )
        info = get_pool(REF)
        assert info.location == "eastus"
        assert info.parent_pool is None
        assert info.address_prefixes == (
            ip_network("10.0.0.0/16"),
            ip_network("10.1.0.0/16"),
        )

    def test_raises_pool_not_found_on_empty_payload(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stdout="null"),
        )
        with pytest.raises(PoolNotFoundError):
            get_pool(REF)

    def test_raises_invocation_error_on_nonzero_exit(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stderr="auth failed", returncode=1),
        )
        with pytest.raises(AzCliInvocationError, match="auth failed"):
            get_pool(REF)

    def test_raises_invocation_error_on_bad_json(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stdout="this is not json"),
        )
        with pytest.raises(AzCliInvocationError, match="non-JSON"):
            get_pool(REF)


class TestListAssociatedResources:
    def test_returns_empty_list_when_no_reservations(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stdout="[]"),
        )
        assert list_associated_resources(REF) == []

    def test_parses_reservations(self, mocker: MockerFixture) -> None:
        mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
        payload = [
            {
                "resourceId": "/subscriptions/.../virtualNetworks/vnet-a",
                "addressPrefixes": ["10.0.0.0/24"],
                "poolId": "/subscriptions/.../ipamPools/prod-pool",
            },
            {
                "resourceId": "/subscriptions/.../virtualNetworks/vnet-b",
                "addressPrefixes": ["10.0.1.0/24", "10.0.2.0/24"],
                "poolId": "/subscriptions/.../ipamPools/prod-pool",
            },
        ]
        mocker.patch(
            "avnm_pool_cidr.ipam.subprocess.run",
            return_value=_fake_completed(stdout=json.dumps(payload)),
        )
        resources = list_associated_resources(REF)
        assert len(resources) == 2
        assert resources[0].address_prefixes == (ip_network("10.0.0.0/24"),)
        assert resources[1].address_prefixes == (
            ip_network("10.0.1.0/24"),
            ip_network("10.0.2.0/24"),
        )
