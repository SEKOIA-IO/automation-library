"""Live integration tests against the PolySwarm API.

Run with: uv run pytest tests/test_integration.py -m integration -v
Requires: POLYSWARM_API_KEY environment variable
"""

import os
from pathlib import Path

import pytest

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_scanfile import ScanFile
from polyswarm_modules.action_polyswarm_scanip import ScanIp
from polyswarm_modules.action_polyswarm_scanurl import ScanUrl
from polyswarm_modules.action_polyswarm_searchhash import SearchHash
from polyswarm_modules.models import PolyswarmModuleConfiguration

EICAR_HASH: str = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"
EICAR_CONTENT: bytes = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

pytestmark = pytest.mark.integration

api_key: str = os.environ.get("POLYSWARM_API_KEY", "")
skip_no_key = pytest.mark.skipif(not api_key, reason="POLYSWARM_API_KEY not set")


@pytest.fixture
def module() -> PolyswarmModule:
    """Override the unit-test fixture with the live API key."""
    module = PolyswarmModule()
    module.configuration = PolyswarmModuleConfiguration(apikey=api_key, community="default")
    return module


@skip_no_key
def test_search_hash(data_storage: str, module: PolyswarmModule) -> None:
    action = SearchHash(module=module, data_path=data_storage)

    response = action.run({"query_hash": EICAR_HASH})

    assert response is not None
    assert response["malicious_detections"] > 0
    assert response["polyscore"] > 0.5
    assert response["permalink"]


@skip_no_key
def test_scan_file(data_storage: str, module: PolyswarmModule) -> None:
    """A file is referenced by name, the way Sekoia delivers it to the module."""
    action = ScanFile(module=module, data_path=data_storage)

    sample = Path(data_storage) / "eicar.com"
    sample.write_bytes(EICAR_CONTENT)

    response = action.run({"file": sample.name})

    assert response is not None, action.error_message
    assert response["sha256"] == EICAR_HASH
    assert response["malicious_count"] > 0
    assert isinstance(response["cached"], bool)


@skip_no_key
def test_scan_file_refuses_a_path_outside_the_data_directory(data_storage: str, module: PolyswarmModule) -> None:
    """Nothing outside the run data directory is uploadable, tokens included."""
    action = ScanFile(module=module, data_path=data_storage)

    response = action.run({"file": "/etc/hosts"})

    assert response is None
    assert action.error_message


@skip_no_key
def test_scan_url(data_storage: str, module: PolyswarmModule) -> None:
    action = ScanUrl(module=module, data_path=data_storage)

    response = action.run({"url": "https://example.com"})

    assert response is not None
    assert response["sha256"]
    assert response["permalink"]
    assert isinstance(response["failed"], bool)
    assert isinstance(response["cached"], bool)


@skip_no_key
def test_scan_ip(data_storage: str, module: PolyswarmModule) -> None:
    action = ScanIp(module=module, data_path=data_storage)

    response = action.run({"ip": "8.8.8.8"})

    assert response is not None
    assert response["ip"] == "8.8.8.8"
    assert response["sha256"]
    assert response["permalink"]
    assert isinstance(response["failed"], bool)
    assert isinstance(response["cached"], bool)
