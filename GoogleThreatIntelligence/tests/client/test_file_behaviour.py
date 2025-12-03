import pytest
from unittest.mock import MagicMock
from googlethreatintelligence.client import VTAPIConnector
import vt


API_KEY = "FAKE_API_KEY"

def test_get_file_behaviour_success(mock_vt_client):
    connector = VTAPIConnector(api_key=API_KEY)
    mock_behaviour = MagicMock()
    mock_behaviour.sandbox_name = "sandbox1"
    mock_behaviour.processes_created = ["proc1", "proc2"]
    mock_behaviour.files_written = []
    mock_vt_client.iterator.return_value = iter([mock_behaviour])

    connector.get_file_behaviour(mock_vt_client)
    result = connector.results[0]
    assert result.status == "SUCCESS"
    assert result.response["behaviours_count"] == 1
    assert result.response["behaviours"][0]["sandbox_name"] == "sandbox1"


@pytest.fixture
def connector():
    return VTAPIConnector(api_key="dummy")


def make_behaviour(
    sandbox_name="DefaultSandbox",
    processes=None,
    files_written=None,
    files_deleted=None,
    registry_keys=None,
    dns_lookups=None,
    ip_traffic=None,
):
    """Helper to create a fake behaviour object."""
    b = MagicMock()
    b.sandbox_name = sandbox_name

    if processes is not None:
        b.processes_created = processes
    if files_written is not None:
        b.files_written = files_written
    if files_deleted is not None:
        b.files_deleted = files_deleted
    if registry_keys is not None:
        b.registry_keys_set = registry_keys
    if dns_lookups is not None:
        b.dns_lookups = dns_lookups
    if ip_traffic is not None:
        b.ip_traffic = ip_traffic

    return b


# -------------------------------------------------------
# 1) SUCCESS: multiple behaviours, all attributes present
# -------------------------------------------------------

def test_get_file_behaviour_success_full_attributes(connector):
    mock_client = MagicMock()

    behaviour1 = make_behaviour(
        sandbox_name="SandboxA",
        processes=[1, 2],
        files_written=["a", "b", "c"],
        files_deleted=["d1"],
        registry_keys=["k1", "k2"],
        dns_lookups=["dns1"],
        ip_traffic=["tcp1", "tcp2"],
    )

    behaviour2 = make_behaviour(
        sandbox_name="SandboxB",
        processes=[],
        files_written=[],
        files_deleted=None,
        registry_keys=None,
        dns_lookups=[],
        ip_traffic=["tcp"],
    )

    mock_client.iterator.return_value = iter([behaviour1, behaviour2])

    connector.file_hash = "abc123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]

    assert result.status == "SUCCESS"
    assert result.response["behaviours_count"] == 2
    assert result.method == "GET"
    assert result.endpoint.endswith("/api/v3/files/abc123/behaviours")

    # Validate behaviour1 extraction
    b1 = result.response["behaviours"][0]
    assert b1["sandbox_name"] == "SandboxA"
    assert b1["processes_created"] == 2
    assert b1["files_written"] == 3
    assert b1["files_deleted"] == 1
    assert b1["registry_keys_set"] == 2
    assert b1["dns_lookups"] == 1
    assert b1["ip_traffic"] == 2

    # Validate behaviour2 minimal fields
    b2 = result.response["behaviours"][1]
    assert b2["sandbox_name"] == "SandboxB"
    assert b2["processes_created"] == 0
    assert b2["files_written"] == 0
    assert b2["dns_lookups"] == 0
    assert b2["ip_traffic"] == 1


# -------------------------------------------------------
# 2) APIError: Premium API missing → NOT_AVAILABLE
# -------------------------------------------------------

def test_get_file_behaviour_api_error(connector, caplog):
    mock_client = MagicMock()

    mock_client.iterator.side_effect = vt.APIError("PremiumError", "Requires Premium")

    connector.file_hash = "123xyz"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]

    assert result.status == "NOT_AVAILABLE"
    assert "Premium API" in result.error
    assert result.method == "GET"

    # Warning should have been logged
    assert "File behaviours not available" in caplog.text
