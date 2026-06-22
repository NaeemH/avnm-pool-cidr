"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Regexes used by `record-fixtures.sh` and re-applied by tests as a defense-in-depth
# check that no real GUIDs sneak into committed fixtures.
GUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
SCRUBBED_GUID = "00000000-0000-0000-0000-000000000000"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture by base name from `tests/fixtures/`.

    Asserts the fixture contains no GUIDs other than the scrubbed all-zero GUID,
    so a careless re-record can't leak a real subscription/tenant ID.
    """
    path = FIXTURES_DIR / f"{name}.json"
    text = path.read_text(encoding="utf-8")
    for match in GUID_RE.findall(text):
        if match.lower() != SCRUBBED_GUID:
            raise AssertionError(
                f"Fixture {name!r} contains unscrubbed GUID {match!r}. "
                f"Re-run scripts/record-fixtures.sh and re-scrub before committing."
            )
    return json.loads(text)


@pytest.fixture
def fixture_loader() -> Any:
    """Test-injectable handle to `load_fixture`."""
    return load_fixture


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def fake_az(mocker: MockerFixture) -> Any:
    """Patch `az` discovery + `subprocess.run` to return queued JSON payloads.

    Usage in a test::

        def test_something(fake_az, fixture_loader):
            fake_az([fixture_loader("pool-show"), fixture_loader("list-associated-populated")])
            ...

    Each call to the patched `subprocess.run` consumes the next queued payload.
    """
    mocker.patch("avnm_pool_cidr.ipam.shutil.which", return_value="/usr/bin/az")
    queue: list[str] = []

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if not queue:
            raise AssertionError(
                "fake_az() ran out of queued payloads -- did the code under test "
                "make more `az` calls than the test expected?"
            )
        return _completed(queue.pop(0))

    mocker.patch("avnm_pool_cidr.ipam.subprocess.run", side_effect=fake_run)

    def enqueue(payloads: list[Any]) -> None:
        queue.extend(json.dumps(p) for p in payloads)

    return enqueue
