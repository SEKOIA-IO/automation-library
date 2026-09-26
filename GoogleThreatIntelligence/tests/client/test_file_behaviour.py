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
    attrs = {"sandbox_name": sandbox_name}

    if processes is not None:
        b.processes_created = processes
        attrs["processes_created"] = processes
    if files_written is not None:
        b.files_written = files_written
        attrs["files_written"] = files_written
    if files_deleted is not None:
        b.files_deleted = files_deleted
        attrs["files_deleted"] = files_deleted
    if registry_keys is not None:
        b.registry_keys_set = registry_keys
        attrs["registry_keys_set"] = registry_keys
    if dns_lookups is not None:
        b.dns_lookups = dns_lookups
        attrs["dns_lookups"] = dns_lookups
    if ip_traffic is not None:
        b.ip_traffic = ip_traffic
        attrs["ip_traffic"] = ip_traffic

    # Match vt-py objects: expose attributes via to_dict()/attributes
    b.to_dict = MagicMock(return_value={"attributes": attrs})

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

    # Validate merged/flattened fields at root level
    assert result.response["file_hash"] == "abc123"
    assert result.response["sandbox_names"] == ["SandboxA", "SandboxB"]
    assert result.response["files_written"] == ["a", "b", "c"]  # merged from all sandboxes
    assert result.response["files_deleted"] == ["d1"]
    assert result.response["dns_lookups"] == ["dns1"]
    assert result.response["ip_traffic"] == ["tcp1", "tcp2", "tcp"]  # merged
    assert result.response["processes_created"] == 2  # sum of processes counts

    # Validate behaviour1 extraction (raw data preserved)
    b1 = result.response["behaviours"][0]
    assert b1["sandbox_name"] == "SandboxA"
    assert b1["processes_created"] == 2
    assert b1["files_written"] == ["a", "b", "c"]
    assert b1["files_deleted"] == ["d1"]
    assert b1["registry_keys_set"] == ["k1", "k2"]
    assert b1["dns_lookups"] == ["dns1"]
    assert b1["ip_traffic"] == ["tcp1", "tcp2"]

    # Validate behaviour2 minimal fields
    b2 = result.response["behaviours"][1]
    assert b2["sandbox_name"] == "SandboxB"
    assert b2["processes_created"] == 0
    assert b2["files_written"] == []
    assert b2["dns_lookups"] == []
    assert b2["ip_traffic"] == ["tcp"]


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


# -------------------------------------------------------
# 3) Edge cases for behaviour_raw without "attributes" key
# -------------------------------------------------------


def test_behaviour_raw_dict_without_attributes(connector):
    """Test behaviour that serializes to a dict without 'attributes' key (L298)."""
    mock_client = MagicMock()

    b = MagicMock()
    b.sandbox_name = "FlatSandbox"
    # to_dict returns a flat dict (no "attributes" wrapper)
    b.to_dict = MagicMock(return_value={
        "id": "beh-1",
        "type": "behaviour",
        "sandbox_name": "FlatSandbox",
        "processes_created": 5,
        "files_written": ["f1"],
    })

    mock_client.iterator.return_value = iter([b])
    connector.file_hash = "flat123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    assert result.status == "SUCCESS"
    beh = result.response["behaviours"][0]
    assert beh["id"] == "beh-1"
    assert beh["type"] == "behaviour"
    assert beh["sandbox_name"] == "FlatSandbox"
    assert beh["processes_created"] == 5
    assert result.response["files_written"] == ["f1"]


def test_behaviour_raw_not_dict(connector):
    """Test behaviour that serializes to a non-dict value (L300)."""
    mock_client = MagicMock()

    b = MagicMock()
    b.sandbox_name = "WS"
    b.to_dict = MagicMock(return_value="raw_string_value")

    mock_client.iterator.return_value = iter([b])
    connector.file_hash = "nd123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    assert result.status == "SUCCESS"
    assert result.response["behaviours_count"] == 1


def test_behaviour_id_from_attrs_fallback(connector):
    """Test id/type taken from behaviour_attrs when not in behaviour_raw (L313)."""
    mock_client = MagicMock()

    b = MagicMock()
    b.sandbox_name = "SB"
    b.to_dict = MagicMock(return_value={
        "attributes": {
            "id": "attr-id",
            "type": "attr-type",
            "sandbox_name": "SB",
        }
    })

    mock_client.iterator.return_value = iter([b])
    connector.file_hash = "fb123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    beh = result.response["behaviours"][0]
    assert beh["id"] == "attr-id"
    assert beh["type"] == "attr-type"


def test_behaviour_processes_created_scalar(connector):
    """Test processes_created as a non-list scalar value (L385-386)."""
    mock_client = MagicMock()

    b = MagicMock()
    b.sandbox_name = "SB"
    b.to_dict = MagicMock(return_value={
        "attributes": {
            "sandbox_name": "SB",
            "processes_created": 7,  # integer, not a list
        }
    })

    mock_client.iterator.return_value = iter([b])
    connector.file_hash = "scalar123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    beh = result.response["behaviours"][0]
    assert beh["processes_created"] == 7
    assert result.response["processes_created"] == 7


def test_behaviour_processes_created_non_numeric_scalar(connector):
    """Test processes_created as a non-numeric scalar (L387 fallback to 0)."""
    mock_client = MagicMock()

    b = MagicMock()
    b.sandbox_name = "SB"
    b.to_dict = MagicMock(return_value={
        "attributes": {
            "sandbox_name": "SB",
            "processes_created": "unknown",
        }
    })

    mock_client.iterator.return_value = iter([b])
    connector.file_hash = "nonnumeric123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    beh = result.response["behaviours"][0]
    assert beh["processes_created"] == "unknown"
    assert result.response["processes_created"] == 0


def test_behaviour_duplicate_sandbox_name(connector):
    """Test sandbox_name deduplication (L375→379)."""
    mock_client = MagicMock()

    b1 = MagicMock()
    b1.sandbox_name = "Same"
    b1.to_dict = MagicMock(return_value={"attributes": {"sandbox_name": "Same"}})

    b2 = MagicMock()
    b2.sandbox_name = "Same"
    b2.to_dict = MagicMock(return_value={"attributes": {"sandbox_name": "Same"}})

    mock_client.iterator.return_value = iter([b1, b2])
    connector.file_hash = "dup123"
    connector.get_file_behaviour(mock_client)

    result = connector.results[-1]
    assert result.response["sandbox_names"] == ["Same"]
