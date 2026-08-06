"""Tests for connector manifest configuration schema."""

import json
import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "account_id",
    [
        "1000",
        "10000",
        "100000",
        "1000000",
        "10001292",
    ],
)
def test_manifest_account_id_accepts_valid_lengths(account_id: str) -> None:
    """Ensure the account_id schema accepts all valid 4-8 digit account identifiers."""
    manifest_path = Path(__file__).resolve().parents[1] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    account_id_pattern = manifest["configuration"]["properties"]["account_id"]["pattern"]

    assert re.fullmatch(account_id_pattern, account_id)
