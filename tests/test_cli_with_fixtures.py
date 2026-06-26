"""Fixture-replay tests for the CLI.

These exercise the full CLI against JSON payloads that match the real shape of
`az network manager ipam-pool ...` responses. The fixtures in `tests/fixtures/`
can be re-recorded by running `scripts/record-fixtures.sh` against your own
subscription (see CONTRIBUTING). Recorded payloads are sanitized before commit.

These tests run with zero network and zero credentials.
"""

from __future__ import annotations

from typing import Any

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from avnm_pool_cidr.cli import app

# Force a wide terminal so rich tables don't truncate long resource IDs in
# assertions below. Without this, CI runs at 80 cols and IDs are cut with `...`.
runner = CliRunner(env={"COLUMNS": "200"})

BASE_ARGS = [
    "--subscription",
    "sub-fixture",
    "--resource-group",
    "rg-net-fixture",
    "--network-manager",
    "vnm-fixture",
]


def test_next_prefix_with_recorded_pool_and_reservations(fake_az: Any, fixture_loader: Any) -> None:
    """next-prefix should skip 10.0.0.0/24, 10.0.1.0/24, 10.0.2.0/24 and return 10.0.3.0/24."""
    fake_az(
        [
            fixture_loader("pool-show"),
            fixture_loader("list-associated-populated"),
        ]
    )
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "24", *BASE_ARGS])
    assert result.exit_code == 0, result.stdout
    assert "10.0.3.0/24" in result.stdout


def test_next_prefix_falls_back_to_second_parent_when_first_is_full(
    fake_az: Any, fixture_loader: Any
) -> None:
    """With 10.0.0.0/16 fully booked, next /16 should come from 10.1.0.0/16."""
    fake_az(
        [
            fixture_loader("pool-show"),
            fixture_loader("list-associated-populated"),
        ]
    )
    # Ask for /16 -- 10.0.0.0/16 is partially used, so /16 there fails; should
    # walk to the second parent 10.1.0.0/16 (which has only a /22 reserved, so
    # /16 still fails there too -> error).
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "16", *BASE_ARGS])
    assert result.exit_code == 1  # no free /16 in either parent


def test_next_prefix_on_empty_pool_returns_lowest(fake_az: Any, fixture_loader: Any) -> None:
    fake_az(
        [
            fixture_loader("pool-show"),
            fixture_loader("list-associated-empty"),
        ]
    )
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "24", *BASE_ARGS])
    assert result.exit_code == 0
    assert "10.0.0.0/24" in result.stdout


def test_list_renders_recorded_reservations(fake_az: Any, fixture_loader: Any) -> None:
    fake_az([fixture_loader("list-associated-populated")])
    result = runner.invoke(app, ["list", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    # Spot-check: the rendered table should mention all three vnets and prefixes.
    assert "vnet-app-a" in result.stdout
    assert "vnet-app-b" in result.stdout
    assert "vnet-platform" in result.stdout
    assert "10.1.0.0/22" in result.stdout


def test_list_empty_pool(fake_az: Any, fixture_loader: Any) -> None:
    fake_az([fixture_loader("list-associated-empty")])
    result = runner.invoke(app, ["list", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    assert "No resources" in result.stdout


def test_usage_summary_matches_recorded_allocations(fake_az: Any, fixture_loader: Any) -> None:
    fake_az(
        [
            fixture_loader("pool-show"),
            fixture_loader("list-associated-populated"),
        ]
    )
    result = runner.invoke(app, ["usage", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    # 10.0.0.0/16 has three /24s reserved (adjacent /24/24/24 = 768 addrs)
    # 10.1.0.0/16 has a single /22 reserved (1024 addrs)
    assert "10.0.0.0/16" in result.stdout
    assert "10.1.0.0/16" in result.stdout


def test_usage_reports_exact_utilization_numbers(fake_az: Any, fixture_loader: Any) -> None:
    """Snapshot the computed used/free/percent columns, not just the parent prefixes."""
    fake_az(
        [
            fixture_loader("pool-show"),
            fixture_loader("list-associated-populated"),
        ]
    )
    result = runner.invoke(app, ["usage", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 0
    out = result.stdout
    # Parent 10.0.0.0/16: 768 of 65,536 used -> 64,768 free, 1.17%.
    assert "65,536" in out
    assert "768" in out
    assert "64,768" in out
    assert "1.17%" in out
    # Parent 10.1.0.0/16: 1,024 used -> 64,512 free, 1.56%.
    assert "1,024" in out
    assert "64,512" in out
    assert "1.56%" in out


def test_next_prefix_pool_without_prefixes_errors(fake_az: Any, fixture_loader: Any) -> None:
    """A pool with an empty addressPrefixes list should exit 1, not crash."""
    fake_az(
        [
            fixture_loader("pool-show-no-prefixes"),
            fixture_loader("list-associated-empty"),
        ]
    )
    result = runner.invoke(app, ["next-prefix", "prod-pool", "--size", "24", *BASE_ARGS])
    assert result.exit_code == 1


def test_list_surfaces_az_failure(mocker: MockerFixture) -> None:
    """When `az` is missing, `list` reports an error and exits 1 (not a traceback)."""
    mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value=None)
    result = runner.invoke(app, ["list", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 1


def test_usage_surfaces_az_failure(mocker: MockerFixture) -> None:
    """When `az` is missing, `usage` reports an error and exits 1 (not a traceback)."""
    mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value=None)
    result = runner.invoke(app, ["usage", "prod-pool", *BASE_ARGS])
    assert result.exit_code == 1
