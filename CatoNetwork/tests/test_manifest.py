"""Tests for connector manifest configuration schema."""

import json
import re
from pathlib import Path


def test_manifest_account_id_accepts_8_digits() -> None:
    """Ensure the account_id schema accepts full 8-digit account identifiers."""
    manifest_path = Path(__file__).resolve().parents[1] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    account_id_pattern = manifest["configuration"]["properties"]["account_id"]["pattern"]

    assert re.match(account_id_pattern, "10001292")
