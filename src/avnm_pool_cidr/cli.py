"""CLI entrypoint for avnm-pool-cidr."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from avnm_pool_cidr.__about__ import __version__
from avnm_pool_cidr.cidr import next_free_prefix, utilization
from avnm_pool_cidr.errors import AvnmPoolCidrError
from avnm_pool_cidr.ipam import PoolRef, get_pool, list_associated_resources

app = typer.Typer(
    name="avnm-pool-cidr",
    help="Pick the next free CIDR prefix from an Azure VNM IPAM pool.",
    no_args_is_help=True,
    add_completion=False,
)

err_console = Console(stderr=True)
out_console = Console()


def _version_callback(value: bool) -> None:
    if value:
        out_console.print(f"avnm-pool-cidr {__version__}")
        raise typer.Exit()


SubscriptionOpt = Annotated[
    str,
    typer.Option(
        "--subscription",
        "-s",
        envvar="AZURE_SUBSCRIPTION_ID",
        help="Azure subscription ID containing the VNM.",
    ),
]
ResourceGroupOpt = Annotated[
    str,
    typer.Option(
        "--resource-group",
        "-g",
        envvar="AZURE_RESOURCE_GROUP",
        help="Resource group containing the network manager.",
    ),
]
NetworkManagerOpt = Annotated[
    str,
    typer.Option(
        "--network-manager",
        "-n",
        envvar="AZURE_NETWORK_MANAGER",
        help="Name of the Azure Virtual Network Manager.",
    ),
]


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """avnm-pool-cidr: query Azure VNM IPAM pools for free CIDR prefixes."""


def _ref(subscription: str, resource_group: str, network_manager: str, pool: str) -> PoolRef:
    return PoolRef(
        subscription=subscription,
        resource_group=resource_group,
        network_manager=network_manager,
        name=pool,
    )


@app.command("next-prefix")
def next_prefix_cmd(
    pool: Annotated[str, typer.Argument(help="IPAM pool name.")],
    size: Annotated[
        int,
        typer.Option(
            "--size",
            help="Requested prefix length, e.g. 24 for a /24.",
        ),
    ],
    subscription: SubscriptionOpt,
    resource_group: ResourceGroupOpt,
    network_manager: NetworkManagerOpt,
) -> None:
    """Print the next free /SIZE prefix in POOL."""
    try:
        ref = _ref(subscription, resource_group, network_manager, pool)
        info = get_pool(ref)
        associated = list_associated_resources(ref)
        allocated = [p for r in associated for p in r.address_prefixes]
        # Try each parent prefix in turn; return the first one with capacity.
        last_err: AvnmPoolCidrError | None = None
        for parent in info.address_prefixes:
            try:
                chosen = next_free_prefix(parent, allocated, size)
                out_console.print(str(chosen))
                return
            except AvnmPoolCidrError as exc:
                last_err = exc
                continue
        if last_err is not None:
            raise last_err
        raise AvnmPoolCidrError(f"Pool {pool!r} has no address prefixes configured")
    except AvnmPoolCidrError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("list")
def list_cmd(
    pool: Annotated[str, typer.Argument(help="IPAM pool name.")],
    subscription: SubscriptionOpt,
    resource_group: ResourceGroupOpt,
    network_manager: NetworkManagerOpt,
) -> None:
    """List every resource that has reserved space from POOL."""
    try:
        ref = _ref(subscription, resource_group, network_manager, pool)
        associated = list_associated_resources(ref)
    except AvnmPoolCidrError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not associated:
        out_console.print(f"No resources are using prefixes from pool {pool!r}.")
        return

    table = Table(title=f"Reservations in IPAM pool {pool!r}")
    table.add_column("Prefix", style="cyan")
    table.add_column("Resource ID", style="white")
    for r in associated:
        prefixes = ", ".join(str(p) for p in r.address_prefixes) or "-"
        table.add_row(prefixes, r.resource_id or "-")
    out_console.print(table)


@app.command("usage")
def usage_cmd(
    pool: Annotated[str, typer.Argument(help="IPAM pool name.")],
    subscription: SubscriptionOpt,
    resource_group: ResourceGroupOpt,
    network_manager: NetworkManagerOpt,
) -> None:
    """Summarize address-level utilization for POOL."""
    try:
        ref = _ref(subscription, resource_group, network_manager, pool)
        info = get_pool(ref)
        associated = list_associated_resources(ref)
    except AvnmPoolCidrError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    allocated = [p for r in associated for p in r.address_prefixes]
    table = Table(title=f"Utilization of IPAM pool {pool!r}")
    table.add_column("Parent prefix", style="cyan")
    table.add_column("Total addrs", justify="right")
    table.add_column("Used addrs", justify="right")
    table.add_column("Free addrs", justify="right")
    table.add_column("% used", justify="right")
    for parent in info.address_prefixes:
        # Only count allocations that overlap *this* parent.
        relevant = [a for a in allocated if a.overlaps(parent)]
        util = utilization(parent, relevant)
        table.add_row(
            str(parent),
            f"{util.total_addresses:,}",
            f"{util.allocated_addresses:,}",
            f"{util.free_addresses:,}",
            f"{util.percent_used:.2f}%",
        )
    out_console.print(table)


if __name__ == "__main__":
    app()
