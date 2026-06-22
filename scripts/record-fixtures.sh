#!/usr/bin/env bash
# Record fresh fixtures for tests/fixtures/ against a real AVNM IPAM pool.
#
# This script is the only thing in the repo that touches a real Azure subscription.
# Run it against YOUR OWN subscription (not a customer's, not PME, not TME).
# It writes scrubbed JSON into tests/fixtures/, ready to commit.
#
# Usage:
#   AZ_SUB=<sub-guid> AZ_RG=<rg> AZ_VNM=<vnm-name> AZ_POOL=<pool-name> \
#     ./scripts/record-fixtures.sh
#
# The script will:
#   1. Confirm you are logged in (az account show)
#   2. Confirm the subscription is NOT a Microsoft-internal tenant (PME/TME guard)
#   3. Fetch pool metadata and reservations
#   4. Scrub: replace your subscription, RG, VNM, pool names with fixture-safe values
#   5. Scrub: replace any other GUIDs with the all-zero scrubbed GUID
#   6. Write to tests/fixtures/*.json
#
# Re-run the test suite before committing to confirm the scrubbed fixtures still
# satisfy the fixture-replay tests.

set -euo pipefail

: "${AZ_SUB:?AZ_SUB (subscription GUID) is required}"
: "${AZ_RG:?AZ_RG (resource group containing the network manager) is required}"
: "${AZ_VNM:?AZ_VNM (network manager name) is required}"
: "${AZ_POOL:?AZ_POOL (IPAM pool name) is required}"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
FIXTURES_DIR="$REPO_ROOT/tests/fixtures"
mkdir -p "$FIXTURES_DIR"

# Sanity: az is installed and logged in.
if ! command -v az >/dev/null 2>&1; then
  echo "error: az CLI not on PATH" >&2
  exit 1
fi
if ! az account show -s "$AZ_SUB" >/dev/null 2>&1; then
  echo "error: not logged in to subscription $AZ_SUB. Run 'az login'." >&2
  exit 1
fi

# Guard: refuse to record from a Microsoft-internal tenant. This is an OSS repo;
# PME/TME data should never land here even after scrubbing.
TENANT_NAME="$(az account show -s "$AZ_SUB" --query 'tenantDisplayName' -o tsv 2>/dev/null || true)"
case "$TENANT_NAME" in
  *Microsoft* | *MSFT* | *PME* | *TME*)
    echo "error: refusing to record from tenant '$TENANT_NAME'." >&2
    echo "       Use a personal/MSDN/PAYG subscription, not a Microsoft-internal one." >&2
    exit 1
    ;;
esac

SCRUBBED_SUB="00000000-0000-0000-0000-000000000000"
SCRUBBED_RG="rg-net-fixture"
SCRUBBED_VNM="vnm-fixture"

scrub() {
  # stdin -> stdout, replacing live identifiers with fixture-safe ones, then
  # blanking out any leftover GUIDs (a defensive second pass).
  sed \
    -e "s|/subscriptions/$AZ_SUB|/subscriptions/$SCRUBBED_SUB|gI" \
    -e "s|$AZ_RG|$SCRUBBED_RG|gI" \
    -e "s|$AZ_VNM|$SCRUBBED_VNM|gI" \
  | python3 -c '
import re, sys
GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
SCRUBBED = "00000000-0000-0000-0000-000000000000"
text = sys.stdin.read()
def keep_or_zero(m: re.Match[str]) -> str:
    return SCRUBBED if m.group(0).lower() != SCRUBBED else SCRUBBED
sys.stdout.write(GUID.sub(keep_or_zero, text))
'
}

echo ">>> Recording pool-show.json from $AZ_VNM/$AZ_POOL ..."
az network manager ipam-pool show \
  --subscription "$AZ_SUB" \
  --resource-group "$AZ_RG" \
  --network-manager-name "$AZ_VNM" \
  --name "$AZ_POOL" \
  -o json \
  | scrub > "$FIXTURES_DIR/pool-show.json"

echo ">>> Recording list-associated.json from $AZ_VNM/$AZ_POOL ..."
az network manager ipam-pool list-associated-resources \
  --subscription "$AZ_SUB" \
  --resource-group "$AZ_RG" \
  --network-manager-name "$AZ_VNM" \
  --pool-name "$AZ_POOL" \
  -o json \
  | scrub > "$FIXTURES_DIR/list-associated-recorded.json"

echo ">>> Done. Inspect these before committing:"
ls -1 "$FIXTURES_DIR"
echo ""
echo ">>> Recommended: 'pytest -q' to confirm the new fixtures still satisfy tests."
echo ">>> NOTE: the canonical 'list-associated-populated.json' is hand-curated for"
echo ">>>       test predictability; do not overwrite it with raw recordings."
