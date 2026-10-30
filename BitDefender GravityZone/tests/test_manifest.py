import json
from pathlib import Path


def test_manifest_api_key_is_declared_as_secret():
    manifest_path = Path(__file__).resolve().parent.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    secrets = manifest["configuration"].get("secrets", [])
    assert "api_key" in secrets
