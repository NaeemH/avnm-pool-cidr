"""CLI integration tests using typer's CliRunner."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from avnm_pool_cidr.cli import app

runner = CliRunner()

POOL_PAYLOAD = {
    "name": "prod-pool",
    "location": "eastus",
    "properties": {
        "addressPrefixes": ["10.0.0.0/16"],
        "parentPoolName": None,
    },
}

RESERVATIONS_PAYLOAD: list[dict[str, Any]] = [
    {
        "resourceId": "/subscriptions/.../virtualNetworks/vnet-a",
        "addressPrefixes": ["10.0.0.0/24"],
        "poolId": "/subscriptions/.../ipamPools/prod-pool",
    },
]

BASE_ARGS = [
    "--subscription",
    "sub-123",
    "--resource-group",
    "rg-net",
    "--network-manager",
    "vnm-prod",
]


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _patch_az_calls(mocker: MockerFixture, payloads: list[str]) -> None:
    """Patch shutil.which + subprocess.run to return the given JSON payloads in order."""
    mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
    iterable = iter(payloads)

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return _completed(next(iterable))

    mocker.patch("avnm_pool_cidr.ipam.subprocess.run", side_effect=fake_run)


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "avnm-pool-cidr" in result.stdout


def test_next_prefix_returns_first_free_subnet(mocker: MockerFixture) -> None:
    _patch_az_calls(
        mocker,
        [json.dumps(POOL_PAYLOAD), json.dumps(RESERVATIONS_PAYLOAD)],
    )
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "24", *BASE_ARGS])
    assert result.exit_code == 0
    assert "10.0.1.0/24" in result.stdout


def test_next_prefix_handles_az_error(mocker: MockerFixture) -> None:
    mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value=None)
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "24", *BASE_ARGS])
    assert result.exit_code == 1
    # rich's Console(stderr=True) writes to stderr, which Typer's CliRunner keeps
    # separate from stdout. Exit code is enough to confirm the error path fired.


def test_list_renders_table(mocker: MockerFixture) -> None:
    _patch_az_calls(mocker, [json.dumps(RESERVATIONS_PAYLOAD)])
    result = runner.invoke(app, ["list", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    assert "10.0.0.0/24" in result.stdout
    assert "vnet-a" in result.stdout


def test_list_empty(mocker: MockerFixture) -> None:
    _patch_az_calls(mocker, ["[]"])
    result = runner.invoke(app, ["list", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    assert "No resources" in result.stdout


def test_usage_renders_table(mocker: MockerFixture) -> None:
    _patch_az_calls(
        mocker,
        [json.dumps(POOL_PAYLOAD), json.dumps(RESERVATIONS_PAYLOAD)],
    )
    result = runner.invoke(app, ["usage", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    assert "10.0.0.0/16" in result.stdout
    assert "65,536" in result.stdout or "65536" in result.stdout
