"""Thin Azure CLI wrapper for AVNM IPAM pool operations.

We shell out to `az` (rather than depending on `azure-mgmt-network` directly) for
the same reason `azkv-ssh-fetch` shells out to `az network bastion`: AVNM IPAM is
a young API, the user's `az` install is the source of truth for auth, and the
operator running this tool already has `az` configured.

All commands here are read-only (`list`, `show`, `list-associated-resources`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from ipaddress import ip_network
from typing import Any

from avnm_pool_cidr.cidr import IPNetwork
from avnm_pool_cidr.errors import (
    AzCliInvocationError,
    AzCliNotFoundError,
    PoolNotFoundError,
)


@dataclass(frozen=True)
class PoolRef:
    """Identifies a single AVNM IPAM pool."""

    subscription: str
    resource_group: str
    network_manager: str
    name: str


@dataclass(frozen=True)
class PoolInfo:
    """Resolved metadata about an IPAM pool."""

    ref: PoolRef
    address_prefixes: tuple[IPNetwork, ...]
    location: str
    parent_pool: str | None


@dataclass(frozen=True)
class AssociatedResource:
    """A resource that has reserved CIDR space from a pool."""

    resource_id: str
    address_prefixes: tuple[IPNetwork, ...]
    pool_id: str | None


def _require_az() -> str:
    """Return the absolute path to `az`, or raise AzCliNotFoundError."""
    path = shutil.which("az")
    if path is None:
        raise AzCliNotFoundError(
            "The Azure CLI (`az`) was not found on PATH. "
            "Install it from https://aka.ms/installazurecli."
        )
    return path


def _run_az_json(args: Sequence[str]) -> Any:
    """Invoke `az <args>` and return parsed JSON, or raise AzCliInvocationError."""
    az = _require_az()
    cmd = [az, *args, "--output", "json"]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AzCliInvocationError(f"failed to execute az: {exc}") from exc

    if completed.returncode != 0:
        raise AzCliInvocationError(
            f"`az {' '.join(args)}` exited {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )

    if not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AzCliInvocationError(
            f"`az {' '.join(args)}` returned non-JSON output: {exc}"
        ) from exc


def get_pool(ref: PoolRef) -> PoolInfo:
    """Fetch metadata for a single IPAM pool."""
    payload = _run_az_json(
        [
            "network",
            "manager",
            "ipam-pool",
            "show",
            "--subscription",
            ref.subscription,
            "--resource-group",
            ref.resource_group,
            "--network-manager-name",
            ref.network_manager,
            "--name",
            ref.name,
        ]
    )
    if not payload:
        raise PoolNotFoundError(f"IPAM pool {ref.name!r} not found")

    props = payload.get("properties", {}) or {}
    prefixes_raw = props.get("addressPrefixes") or []
    prefixes = tuple(ip_network(p, strict=True) for p in prefixes_raw)
    location = payload.get("location", "")
    parent_pool = props.get("parentPoolName")
    return PoolInfo(
        ref=ref,
        address_prefixes=prefixes,
        location=location,
        parent_pool=parent_pool,
    )


def list_associated_resources(ref: PoolRef) -> list[AssociatedResource]:
    """List every resource that has claimed space from the pool."""
    payload = (
        _run_az_json(
            [
                "network",
                "manager",
                "ipam-pool",
                "list-associated-resources",
                "--subscription",
                ref.subscription,
                "--resource-group",
                ref.resource_group,
                "--network-manager-name",
                ref.network_manager,
                "--pool-name",
                ref.name,
            ]
        )
        or []
    )

    out: list[AssociatedResource] = []
    for item in payload:
        prefixes = tuple(ip_network(p, strict=True) for p in (item.get("addressPrefixes") or []))
        out.append(
            AssociatedResource(
                resource_id=item.get("resourceId", ""),
                address_prefixes=prefixes,
                pool_id=item.get("poolId"),
            )
        )
    return out
