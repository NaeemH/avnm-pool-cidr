# avnm-pool-cidr

[![CI](https://github.com/NaeemH/avnm-pool-cidr/actions/workflows/ci.yml/badge.svg)](https://github.com/NaeemH/avnm-pool-cidr/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/avnm-pool-cidr.svg)](https://pypi.org/project/avnm-pool-cidr/)
[![Python](https://img.shields.io/pypi/pyversions/avnm-pool-cidr.svg)](https://pypi.org/project/avnm-pool-cidr/)
[![Downloads](https://static.pepy.tech/badge/avnm-pool-cidr)](https://pepy.tech/project/avnm-pool-cidr)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Pick the next free CIDR prefix from an **Azure Virtual Network Manager (AVNM)
IPAM pool** &mdash; without manually scrolling through the Azure portal or writing yet
another `ipaddress`-and-`az`-CLI bash one-liner.

## Why

AVNM IPAM is the right way to centralize CIDR allocation across an Azure tenant,
but the day-to-day operator workflow ("give me a free `/24` from `prod-pool`") is
not yet a first-class CLI verb in `az`. This tool fills the gap with three
focused commands.

## Install

```bash
pipx install avnm-pool-cidr
```

You need `az` on your PATH and a current Azure login (`az login`). Auth is
delegated entirely to the Azure CLI &mdash; this tool does not embed credentials.

## Usage

All commands take the same three locator options (each also reads from an
environment variable):

| Option | Env var | Description |
|---|---|---|
| `--subscription`/`-s` | `AZURE_SUBSCRIPTION_ID` | Subscription containing the VNM |
| `--resource-group`/`-g` | `AZURE_RESOURCE_GROUP` | RG containing the network manager |
| `--network-manager`/`-n` | `AZURE_NETWORK_MANAGER` | Name of the network manager |

```bash
# 1. Find the next free /24 in prod-pool
apc next-prefix prod-pool --size 24 \
  -s 11111111-1111-1111-1111-111111111111 \
  -g rg-network -n vnm-prod
# -> 10.0.5.0/24

# 2. List every resource that has reserved space from prod-pool
apc list prod-pool -s ... -g rg-network -n vnm-prod

# 3. Show address-level utilization (per parent prefix)
apc usage prod-pool -s ... -g rg-network -n vnm-prod
```

The short alias `apc` is installed alongside `avnm-pool-cidr`.

## How it works

`avnm-pool-cidr` shells out to `az network manager ipam-pool` for the
authoritative pool/reservation data, then does the CIDR math in pure Python
(`ipaddress` stdlib). Splitting it this way keeps the math trivial to unit-test
and means the tool inherits whatever auth, proxy, and ARM endpoint settings your
`az` install already has.

## Companion tool

This is the second tool in a series of small Azure operator CLIs. The first is
[`azkv-ssh-fetch`](https://pypi.org/project/azkv-ssh-fetch/) &mdash; for fetching
SSH private keys from Key Vault and connecting through Azure Bastion in one step.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

ruff check . && ruff format --check .
mypy src
pytest --cov
```

## License

MIT &copy; 2026 Naeem Hossain
