"""Unit tests for SentinelOneDeviceAssetConnector."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.module import Module

from sentinelone_module.asset_connector.device_assets import SentinelOneDeviceAssetConnector
from sentinelone_module.asset_connector.models import SentinelOneAgent, NetworkInterface, Location


@pytest.fixture
def test_sentinelone_device_asset_connector(data_storage):
    """Create a test SentinelOne device asset connector."""
    module = Module()
    module.configuration = {
        "hostname": "https://example.sentinelone.net",
        "api_token": "fake_sentinelone_api_key",
    }

    connector = SentinelOneDeviceAssetConnector(module=module, data_path=data_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    connector.log = Mock()
    connector.log_exception = Mock()

    # Patch the client to avoid actual initialization
    mock_client = Mock()
    with patch.object(type(connector), "client", property(lambda self: mock_client)):
        connector._client_mock = mock_client
        yield connector


@pytest.fixture
def sample_agent():
    """Create a sample SentinelOne agent."""
    return SentinelOneAgent(
        id="225494730938493804",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="225494730938493804",
        accountName="Test Account",
        siteId="225494730938493804",
        siteName="Test Site",
        groupId="225494730938493804",
        groupName="Test Group",
        uuid="ff819e70af13be381993075eb0ce5f2f6de05be2",
        agentVersion="2.5.0.2417",
        networkInterfaces=[
            NetworkInterface(
                id="1",
                name="eth0",
                physical="00:25:96:FF:FE:12:34:56",
                inet=["192.168.1.100"],
                inet6=["fe80::1"],
                gatewayMacAddress="00:25:96:FF:FE:12",
                gatewayIp="192.168.1.1",
            )
        ],
        domain="mybusiness.net",
        computerName="JOHN-WIN-4125",
        osName="Windows 10",
        osRevision="1909",
        osArch="32 bit",
        osUsername="john.doe",
        osStartTime="2018-02-20T10:30:00.000000Z",
        osType="windows",
        totalMemory=8192,
        modelName="Acme computers - 15x4k",
        machineType="desktop",
        cpuId="Acme chips inc. Pro5555 @ 3.33GHz",
        cpuCount=2,
        coreCount=8,
        externalIp="31.155.5.7",
        groupIp="31.155.5.x",
        activeThreats=0,
        infected=False,
        threatRebootRequired=False,
        lastActiveDate="2018-02-27T04:49:26.257525Z",
        isActive=True,
        isUpToDate=True,
        networkStatus="connected",
        registeredAt="2018-02-27T04:49:26.257525Z",
        isPendingUninstall=False,
        isUninstalled=False,
        isDecommissioned=False,
        lastLoggedInUserName="janedoe3",
        scanStatus="none",
        mitigationMode="detect",
        networkQuarantineEnabled=False,
        firewallEnabled=True,
        locations=[Location(id="loc-1", name="New York Office", scope="group")],
        proxyStates={"httpProxyEnabled": None, "httpsProxyEnabled": False},
        containerizedWorkloadCounts={"total": None, "running": 0, "stopped": 0},
    )


# Tests for fetch_agents method
def test_fetch_agents_success(test_sentinelone_device_asset_connector, sample_agent):
    """Test successful agent fetching."""
    # Arrange
    mock_response = {
        "data": [sample_agent.model_dump()],
        "errors": None,
        "pagination": {"nextCursor": "YWdlbnRfaWQ6NTgwMjkzODE=", "totalItems": 1},
    }

    test_sentinelone_device_asset_connector._client_mock.get.return_value = mock_response

    # Act
    agents, next_cursor = test_sentinelone_device_asset_connector.fetch_agents()

    # Assert
    assert len(agents) == 1
    assert agents[0].id == sample_agent.id
    assert agents[0].computerName == sample_agent.computerName
    assert next_cursor == "YWdlbnRfaWQ6NTgwMjkzODE="
    test_sentinelone_device_asset_connector._client_mock.get.assert_called_once_with(
        "/web/api/v2.1/agents", params={"limit": 100}
    )


def test_fetch_agents_no_response(test_sentinelone_device_asset_connector):
    """Test fetching agents with no response."""
    # Arrange
    test_sentinelone_device_asset_connector._client_mock.get.side_effect = Exception("Connection error")

    # Act
    agents, next_cursor = test_sentinelone_device_asset_connector.fetch_agents()

    # Assert
    assert agents == []
    assert next_cursor is None


def test_fetch_agents_with_errors(test_sentinelone_device_asset_connector, sample_agent):
    """Test fetching agents with errors in response."""
    # Arrange
    mock_response = {
        "data": [sample_agent.model_dump()],
        "errors": ["Some error occurred"],
        "pagination": {"nextCursor": None},
    }

    test_sentinelone_device_asset_connector._client_mock.get.return_value = mock_response

    # Act
    agents, next_cursor = test_sentinelone_device_asset_connector.fetch_agents()

    # Assert
    assert len(agents) == 1
    assert next_cursor is None


def test_fetch_agents_exception(test_sentinelone_device_asset_connector):
    """Test exception handling during agent fetching."""
    # Arrange
    test_sentinelone_device_asset_connector._client_mock.get.side_effect = Exception("API Error")

    # Act
    agents, next_cursor = test_sentinelone_device_asset_connector.fetch_agents()

    # Assert
    assert agents == []
    assert next_cursor is None


# Tests for list_all_agents method
def test_list_all_agents_success(test_sentinelone_device_asset_connector, sample_agent):
    """Test listing all agents with pagination."""
    # Arrange
    agent2 = sample_agent.model_copy()
    agent2.id = "225494730938493805"
    agent2.computerName = "JANE-MAC-5678"
    agent2.createdAt = "2018-02-28T04:49:26.257525Z"

    with patch.object(test_sentinelone_device_asset_connector, "fetch_agents") as mock_fetch:
        mock_fetch.side_effect = [
            ([sample_agent], "cursor1"),
            ([agent2], None),
        ]

        # Act
        agents = test_sentinelone_device_asset_connector.list_all_agents()

        # Assert
        assert len(agents) == 2
        assert agents[0].id == sample_agent.id
        assert agents[1].id == agent2.id
        assert mock_fetch.call_count == 2


def test_list_all_agents_no_pagination(test_sentinelone_device_asset_connector, sample_agent):
    """Test listing agents without pagination."""
    # Arrange
    with patch.object(test_sentinelone_device_asset_connector, "fetch_agents") as mock_fetch:
        mock_fetch.return_value = ([sample_agent], None)

        # Act
        agents = test_sentinelone_device_asset_connector.list_all_agents()

        # Assert
        assert len(agents) == 1
        assert agents[0].id == sample_agent.id
        mock_fetch.assert_called_once()


# Tests for get_device_os method
@pytest.mark.parametrize(
    "os_type,os_name,os_revision,expected_name,expected_type,expected_type_id",
    [
        ("windows", "Windows 10", "1909", "Windows 10 1909", OSTypeStr.WINDOWS, OSTypeId.WINDOWS),
        ("macos", "macOS Monterey", "12.0", "macOS Monterey 12.0", OSTypeStr.MACOS, OSTypeId.MACOS),
        ("linux", "Ubuntu", "20.04", "Ubuntu 20.04", OSTypeStr.LINUX, OSTypeId.LINUX),
        ("unknown", "UnknownOS", "1.0", "UnknownOS 1.0", OSTypeStr.OTHER, OSTypeId.OTHER),
        (None, None, None, "Unknown", OSTypeStr.OTHER, OSTypeId.OTHER),
    ],
)
def test_get_device_os(
    test_sentinelone_device_asset_connector,
    os_type,
    os_name,
    os_revision,
    expected_name,
    expected_type,
    expected_type_id,
):
    """Test OS mapping for various operating systems."""
    os = test_sentinelone_device_asset_connector.get_device_os(os_type, os_name, os_revision)

    assert os.name == expected_name
    assert os.type == expected_type
    assert os.type_id == expected_type_id


# Tests for get_device_type method
@pytest.mark.parametrize(
    "machine_type,expected_type,expected_id",
    [
        ("desktop", DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        ("laptop", DeviceTypeStr.LAPTOP, DeviceTypeId.LAPTOP),
        ("server", DeviceTypeStr.SERVER, DeviceTypeId.SERVER),
        ("unknown", DeviceTypeStr.OTHER, DeviceTypeId.OTHER),
        (None, DeviceTypeStr.OTHER, DeviceTypeId.OTHER),
    ],
)
def test_get_device_type(test_sentinelone_device_asset_connector, machine_type, expected_type, expected_id):
    """Test device type mapping."""
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type(machine_type)

    assert device_type == expected_type
    assert device_id == expected_id


# Tests for map_fields method
def test_map_fields_success(test_sentinelone_device_asset_connector, sample_agent):
    """Test successful field mapping with all fields populated."""
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Basic OCSF fields
    assert isinstance(result, DeviceOCSFModel)
    assert result.activity_name == "Collect"
    assert result.category_name == "Discovery"
    assert result.class_name == "Device Inventory Info"
    assert result.severity == "Informational"

    # Device identification
    assert result.device.hostname == "JOHN-WIN-4125"
    assert result.device.uid == "ff819e70af13be381993075eb0ce5f2f6de05be2"
    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP

    # Operating system
    assert result.device.os.name == "Windows 10 1909"
    assert result.device.os.type == OSTypeStr.WINDOWS

    # Metadata
    assert result.metadata.product.name == "SentinelOne"
    assert result.metadata.product.vendor_name == "SentinelOne"
    assert result.metadata.product.version == "2.5.0.2417"

    # Enhanced fields
    assert result.device.domain == "mybusiness.net"
    assert result.device.ip == "31.155.5.7"
    assert result.device.subnet == "31.155.5.x"
    assert result.device.model == "Acme computers - 15x4k"
    assert result.device.vendor_name == "SentinelOne"
    assert result.device.is_managed is True
    assert result.device.is_compliant is True
    assert result.device.region == "Test Site"
    assert result.device.created_time is not None
    assert result.device.first_seen_time is not None
    assert result.device.last_seen_time is not None
    assert result.device.boot_time is not None
    assert result.device.uid_alt == "225494730938493804"

    # Location
    assert result.device.location is not None
    assert result.device.location.city == "New York Office"

    # Groups
    assert result.device.groups is not None
    assert len(result.device.groups) == 1
    assert result.device.groups[0].name == "Test Group"
    assert result.device.groups[0].uid == "225494730938493804"

    # Network interfaces
    assert result.device.network_interfaces is not None
    assert len(result.device.network_interfaces) == 1
    assert result.device.network_interfaces[0].name == "eth0"
    assert result.device.network_interfaces[0].mac == "00:25:96:FF:FE:12:34:56"
    assert result.device.network_interfaces[0].ip == "192.168.1.100"
    assert result.device.network_interfaces[0].uid == "1"

    # Enrichments
    assert result.enrichments is not None
    assert len(result.enrichments) == 5  # Firewall, Users, Update Status, Active Threats, Infection Status

    # Firewall enrichment
    firewall_enrichment = next((e for e in result.enrichments if e.name == "Firewall"), None)
    assert firewall_enrichment is not None
    assert firewall_enrichment.value == "Enabled"
    assert firewall_enrichment.data.Firewall_status == "Enabled"

    # Users enrichment
    users_enrichment = next((e for e in result.enrichments if e.name == "Users"), None)
    assert users_enrichment is not None
    assert "janedoe3" in users_enrichment.value
    assert "john.doe" in users_enrichment.value
    assert users_enrichment.data.Users == ["janedoe3", "john.doe"]

    # Update Status enrichment
    update_enrichment = next((e for e in result.enrichments if e.name == "Update Status"), None)
    assert update_enrichment is not None
    assert update_enrichment.value == "Up to Date"

    # Active Threats enrichment
    threats_enrichment = next((e for e in result.enrichments if e.name == "Active Threats"), None)
    assert threats_enrichment is not None
    assert threats_enrichment.value == "0"

    # Infection Status enrichment
    infection_enrichment = next((e for e in result.enrichments if e.name == "Infection Status"), None)
    assert infection_enrichment is not None
    assert infection_enrichment.value == "Clean"


def test_map_fields_no_network_interface(test_sentinelone_device_asset_connector, sample_agent):
    """Test field mapping without network interface."""
    sample_agent.networkInterfaces = None
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "JOHN-WIN-4125"
    assert result.device.uid == "ff819e70af13be381993075eb0ce5f2f6de05be2"
    assert result.device.network_interfaces is None

    # Other enhanced fields should still be populated
    assert result.device.domain == "mybusiness.net"
    assert result.device.ip == "31.155.5.7"
    assert result.device.model == "Acme computers - 15x4k"


def test_map_fields_minimal_agent(test_sentinelone_device_asset_connector):
    """Test field mapping with minimal agent data."""
    minimal_agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="MINIMAL-PC",
    )
    result = test_sentinelone_device_asset_connector.map_fields(minimal_agent)

    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "MINIMAL-PC"
    assert result.device.uid == "abc-def-ghi"
    assert result.device.type == DeviceTypeStr.OTHER
    assert result.device.os.type == OSTypeStr.OTHER

    # Optional enhanced fields should be None when not provided
    assert result.device.domain is None
    assert result.device.ip is None
    assert result.device.model is None
    assert result.device.network_interfaces is None
    assert result.device.region is None
    assert result.device.first_seen_time is None
    assert result.device.last_seen_time is None
    assert result.device.is_compliant is None

    # These fields should always be set
    assert result.device.vendor_name == "SentinelOne"
    assert result.device.is_managed is True
    assert result.device.created_time is not None


def test_map_fields_network_interfaces_multiple(test_sentinelone_device_asset_connector):
    """Test field mapping with multiple network interfaces."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="MULTI-NIC-PC",
        networkInterfaces=[
            NetworkInterface(
                id="iface-1", name="eth0", physical="00:11:22:33:44:55", inet=["192.168.1.100", "10.0.0.50"]
            ),
            NetworkInterface(id="iface-2", name="wlan0", physical="AA:BB:CC:DD:EE:FF", inet=["192.168.1.101"]),
            NetworkInterface(id="iface-3", name="lo", physical=None, inet=["127.0.0.1"]),
        ],
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.network_interfaces is not None
    assert len(result.device.network_interfaces) == 3

    # First interface (multiple IPs - should use first one)
    assert result.device.network_interfaces[0].name == "eth0"
    assert result.device.network_interfaces[0].mac == "00:11:22:33:44:55"
    assert result.device.network_interfaces[0].ip == "192.168.1.100"
    assert result.device.network_interfaces[0].uid == "iface-1"

    # Second interface
    assert result.device.network_interfaces[1].name == "wlan0"
    assert result.device.network_interfaces[1].mac == "AA:BB:CC:DD:EE:FF"
    assert result.device.network_interfaces[1].ip == "192.168.1.101"

    # Third interface (no MAC)
    assert result.device.network_interfaces[2].name == "lo"
    assert result.device.network_interfaces[2].mac is None
    assert result.device.network_interfaces[2].ip == "127.0.0.1"


def test_map_fields_network_interface_no_ip(test_sentinelone_device_asset_connector):
    """Test field mapping with network interface but no IP addresses."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="NO-IP-PC",
        networkInterfaces=[NetworkInterface(id="iface-1", name="eth0", physical="00:11:22:33:44:55", inet=None)],
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.network_interfaces is not None
    assert len(result.device.network_interfaces) == 1
    assert result.device.network_interfaces[0].name == "eth0"
    assert result.device.network_interfaces[0].mac == "00:11:22:33:44:55"
    assert result.device.network_interfaces[0].ip is None
    assert result.device.network_interfaces[0].uid == "iface-1"


def test_map_fields_timestamps(test_sentinelone_device_asset_connector):
    """Test field mapping with various timestamp fields."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="TIMESTAMP-PC",
        registeredAt="2018-02-20T10:00:00.000000Z",
        lastActiveDate="2018-02-27T03:00:00.000000Z",
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.created_time is not None
    assert result.device.first_seen_time is not None
    assert result.device.last_seen_time is not None

    # Verify timestamps are different
    assert result.device.created_time != result.device.first_seen_time
    assert result.device.created_time != result.device.last_seen_time

    # Verify first_seen (registered) is before created
    assert result.device.first_seen_time < result.device.created_time


@pytest.mark.parametrize(
    "is_up_to_date,expected_compliant",
    [
        (True, True),
        (False, False),
        (None, None),
    ],
)
def test_map_fields_compliance_status(test_sentinelone_device_asset_connector, is_up_to_date, expected_compliant):
    """Test field mapping with different compliance statuses."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="COMPLIANT-PC",
        isUpToDate=is_up_to_date,
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.is_compliant is expected_compliant
    assert result.device.is_managed is True


@pytest.mark.parametrize(
    "agent_id,computer_name,error_match",
    [
        ("", "TEST-PC", "Agent ID is required"),
        ("123", None, "Computer name is required"),
    ],
)
def test_map_fields_missing_required_fields(
    test_sentinelone_device_asset_connector, agent_id, computer_name, error_match
):
    """Test field mapping with missing required fields raises ValueError."""
    agent = SentinelOneAgent(
        id=agent_id,
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc",
        computerName=computer_name,
    )

    with pytest.raises(ValueError, match=error_match):
        test_sentinelone_device_asset_connector.map_fields(agent)


# Tests for get_assets method
def test_get_assets_success(test_sentinelone_device_asset_connector, sample_agent):
    """Test successful asset generation."""
    # Arrange
    agent2 = sample_agent.model_copy()
    agent2.id = "225494730938493805"
    agent2.computerName = "JANE-MAC-5678"

    test_sentinelone_device_asset_connector._data_path = MagicMock()
    test_sentinelone_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with patch.object(test_sentinelone_device_asset_connector, "list_all_agents") as mock_list:
        mock_list.return_value = [sample_agent, agent2]

        # Act
        assets = list(test_sentinelone_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 2
        assert assets[0].device.hostname == "JOHN-WIN-4125"
        assert assets[1].device.hostname == "JANE-MAC-5678"
        mock_list.assert_called_once()


def test_get_assets_with_mapping_error(test_sentinelone_device_asset_connector, sample_agent):
    """Test asset generation with mapping error."""
    # Arrange
    bad_agent = sample_agent.model_copy()
    bad_agent.id = ""  # This will cause a ValueError

    good_agent = sample_agent.model_copy()
    good_agent.computerName = "GOOD-PC"

    test_sentinelone_device_asset_connector._data_path = MagicMock()
    test_sentinelone_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with patch.object(test_sentinelone_device_asset_connector, "list_all_agents") as mock_list:
        mock_list.return_value = [bad_agent, good_agent]

        # Act
        assets = list(test_sentinelone_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 1  # Only the good agent
        assert assets[0].device.hostname == "GOOD-PC"


def test_get_assets_empty_list(test_sentinelone_device_asset_connector):
    """Test asset generation with empty agent list."""
    # Arrange
    test_sentinelone_device_asset_connector._data_path = MagicMock()
    test_sentinelone_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with patch.object(test_sentinelone_device_asset_connector, "list_all_agents") as mock_list:
        mock_list.return_value = []

        # Act
        assets = list(test_sentinelone_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 0


# Tests for checkpoint management
def test_get_last_created_date(test_sentinelone_device_asset_connector, sample_agent):
    """Test getting last created date from agents."""
    # Arrange
    agent1 = sample_agent.model_copy()
    agent1.createdAt = "2018-02-27T04:49:26.257525Z"

    agent2 = sample_agent.model_copy()
    agent2.createdAt = "2018-02-28T04:49:26.257525Z"

    agent3 = sample_agent.model_copy()
    agent3.createdAt = "2018-02-26T04:49:26.257525Z"

    # Act
    last_date = test_sentinelone_device_asset_connector.get_last_created_date([agent1, agent2, agent3])

    # Assert
    assert last_date == "2018-02-28T04:49:26.257525Z"


def test_get_last_created_date_empty_list(test_sentinelone_device_asset_connector):
    """Test getting last created date from empty list raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="Cannot get last created date from empty agents list"):
        test_sentinelone_device_asset_connector.get_last_created_date([])


def test_update_checkpoint_success(test_sentinelone_device_asset_connector):
    """Test successful checkpoint update."""
    # Arrange
    test_sentinelone_device_asset_connector.new_most_recent_date = "2018-02-28T04:49:26.257525Z"
    mock_cache = {}

    # Mock the context manager
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_cache)
    mock_context.__exit__ = MagicMock(return_value=None)
    test_sentinelone_device_asset_connector.context = mock_context

    # Act
    test_sentinelone_device_asset_connector.update_checkpoint()

    # Assert
    assert mock_cache["most_recent_date_seen"] == "2018-02-28T04:49:26.257525Z"
    mock_context.__enter__.assert_called_once()
    mock_context.__exit__.assert_called_once()


def test_update_checkpoint_none_date(test_sentinelone_device_asset_connector):
    """Test checkpoint update with None date."""
    # Arrange
    test_sentinelone_device_asset_connector.new_most_recent_date = None

    # Act
    test_sentinelone_device_asset_connector.update_checkpoint()

    # Assert
    test_sentinelone_device_asset_connector.log.assert_called_with(
        "Warning: new_most_recent_date is None, skipping checkpoint update", level="warning"
    )


def test_most_recent_date_seen_property(test_sentinelone_device_asset_connector):
    """Test the most_recent_date_seen property."""
    # Arrange
    mock_cache = {"most_recent_date_seen": "2018-02-27T04:49:26.257525Z"}
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_cache)
    mock_context.__exit__ = MagicMock(return_value=None)
    test_sentinelone_device_asset_connector.context = mock_context

    # Act
    result = test_sentinelone_device_asset_connector.most_recent_date_seen

    # Assert
    assert result == "2018-02-27T04:49:26.257525Z"
    mock_context.__enter__.assert_called_once()
    mock_context.__exit__.assert_called_once()


def test_most_recent_date_seen_none(test_sentinelone_device_asset_connector):
    """Test the most_recent_date_seen property when no date is set."""
    # Arrange
    mock_cache = {}
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_cache)
    mock_context.__exit__ = MagicMock(return_value=None)
    test_sentinelone_device_asset_connector.context = mock_context

    # Act
    result = test_sentinelone_device_asset_connector.most_recent_date_seen

    # Assert
    assert result is None
    mock_context.__enter__.assert_called_once()
    mock_context.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "firewall_enabled,expected_status,expected_enrichments",
    [
        (True, "Enabled", True),
        (False, "Disabled", True),
        (None, None, False),
    ],
    ids=["firewall_enabled", "firewall_disabled", "firewall_unknown"],
)
def test_map_fields_firewall_enrichment(
    test_sentinelone_device_asset_connector, sample_agent, firewall_enabled, expected_status, expected_enrichments
):
    """Test that firewall status is properly enriched in the OCSF model."""
    # Arrange
    agent = sample_agent.model_copy(update={"firewallEnabled": firewall_enabled})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    if expected_enrichments:
        firewall_enrichment = next((e for e in result.enrichments if e.name == "Firewall"), None)
        assert firewall_enrichment is not None
        assert firewall_enrichment.value == expected_status
        assert firewall_enrichment.data.Firewall_status == expected_status
    else:
        firewall_enrichment = next((e for e in result.enrichments if e.name == "Firewall"), None)
        assert firewall_enrichment is None


def test_map_fields_groups(test_sentinelone_device_asset_connector, sample_agent):
    """Test that group information is properly mapped."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert result.device.groups is not None
    assert len(result.device.groups) == 1
    assert result.device.groups[0].name == "Test Group"
    assert result.device.groups[0].uid == "225494730938493804"


def test_map_fields_groups_no_group_name(test_sentinelone_device_asset_connector, sample_agent):
    """Test group mapping when only groupId is available."""
    # Arrange
    agent = sample_agent.model_copy(update={"groupName": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.groups is not None
    assert len(result.device.groups) == 1
    assert result.device.groups[0].name == "Unknown"
    assert result.device.groups[0].uid == "225494730938493804"


def test_map_fields_no_groups(test_sentinelone_device_asset_connector, sample_agent):
    """Test mapping when no group information is available."""
    # Arrange
    agent = sample_agent.model_copy(update={"groupName": None, "groupId": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.groups is None


def test_map_fields_boot_time(test_sentinelone_device_asset_connector, sample_agent):
    """Test that boot time is properly parsed and mapped."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert result.device.boot_time is not None
    # Verify it's an integer timestamp
    assert isinstance(result.device.boot_time, int)
    # The expected timestamp for "2018-02-20T10:30:00.000000Z"
    from dateutil.parser import isoparse

    expected_timestamp = int(isoparse("2018-02-20T10:30:00.000000Z").timestamp())
    assert result.device.boot_time == expected_timestamp


def test_map_fields_no_boot_time(test_sentinelone_device_asset_connector, sample_agent):
    """Test mapping when boot time is not available."""
    # Arrange
    agent = sample_agent.model_copy(update={"osStartTime": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.boot_time is None


def test_map_fields_users_enrichment(test_sentinelone_device_asset_connector, sample_agent):
    """Test that user information is properly enriched."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    users_enrichment = next((e for e in result.enrichments if e.name == "Users"), None)
    assert users_enrichment is not None
    assert "janedoe3" in users_enrichment.value
    assert "john.doe" in users_enrichment.value
    assert len(users_enrichment.data.Users) == 2
    assert "janedoe3" in users_enrichment.data.Users
    assert "john.doe" in users_enrichment.data.Users


def test_map_fields_users_enrichment_no_duplicates(test_sentinelone_device_asset_connector, sample_agent):
    """Test that duplicate usernames are not included in enrichment."""
    # Arrange - set both usernames to the same value
    agent = sample_agent.model_copy(update={"lastLoggedInUserName": "john.doe", "osUsername": "john.doe"})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    users_enrichment = next((e for e in result.enrichments if e.name == "Users"), None)
    assert users_enrichment is not None
    assert users_enrichment.value == "john.doe"
    assert len(users_enrichment.data.Users) == 1
    assert users_enrichment.data.Users[0] == "john.doe"


def test_map_fields_no_users_enrichment(test_sentinelone_device_asset_connector, sample_agent):
    """Test that no users enrichment is created when user information is missing."""
    # Arrange
    agent = sample_agent.model_copy(update={"lastLoggedInUserName": None, "osUsername": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    users_enrichment = next((e for e in result.enrichments if e.name == "Users"), None)
    assert users_enrichment is None


def test_map_fields_uid_alt(test_sentinelone_device_asset_connector, sample_agent):
    """Test that uid_alt is set when uuid is used as primary uid."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert result.device.uid == "ff819e70af13be381993075eb0ce5f2f6de05be2"  # uuid
    assert result.device.uid_alt == "225494730938493804"  # id


def test_map_fields_no_uid_alt(test_sentinelone_device_asset_connector, sample_agent):
    """Test that uid_alt is None when uuid is not available."""
    # Arrange - remove uuid so id becomes primary uid
    agent = sample_agent.model_copy(update={"uuid": ""})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.uid == "225494730938493804"  # id
    assert result.device.uid_alt is None


def test_map_fields_subnet(test_sentinelone_device_asset_connector, sample_agent):
    """Test that subnet (groupIp) is properly mapped."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert result.device.subnet == "31.155.5.x"


def test_map_fields_location(test_sentinelone_device_asset_connector, sample_agent):
    """Test that location is properly mapped from locations list."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert result.device.location is not None
    assert result.device.location.city == "New York Office"
    assert result.device.location.country is None  # Not provided by SentinelOne


def test_map_fields_multiple_locations(test_sentinelone_device_asset_connector, sample_agent):
    """Test that first location is used when multiple locations exist."""
    # Arrange
    agent = sample_agent.model_copy(
        update={
            "locations": [
                Location(id="loc-1", name="New York Office", scope="group"),
                Location(id="loc-2", name="London Office", scope="account"),
            ]
        }
    )

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.location is not None
    assert result.device.location.city == "New York Office"


def test_map_fields_no_location(test_sentinelone_device_asset_connector, sample_agent):
    """Test that location is None when no locations are available."""
    # Arrange
    agent = sample_agent.model_copy(update={"locations": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.location is None


def test_map_fields_empty_locations_list(test_sentinelone_device_asset_connector, sample_agent):
    """Test that location is None when locations list is empty."""
    # Arrange
    agent = sample_agent.model_copy(update={"locations": []})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    assert result.device.location is None


def test_map_fields_update_status_enrichment(test_sentinelone_device_asset_connector, sample_agent):
    """Test that update status is properly enriched."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    update_enrichment = next((e for e in result.enrichments if e.name == "Update Status"), None)
    assert update_enrichment is not None
    assert update_enrichment.value == "Up to Date"


def test_map_fields_update_status_required(test_sentinelone_device_asset_connector, sample_agent):
    """Test that update required status is properly enriched."""
    # Arrange
    agent = sample_agent.model_copy(update={"isUpToDate": False})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    update_enrichment = next((e for e in result.enrichments if e.name == "Update Status"), None)
    assert update_enrichment is not None
    assert update_enrichment.value == "Update Required"


def test_map_fields_active_threats_enrichment(test_sentinelone_device_asset_connector, sample_agent):
    """Test that active threats count is properly enriched."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    threats_enrichment = next((e for e in result.enrichments if e.name == "Active Threats"), None)
    assert threats_enrichment is not None
    assert threats_enrichment.value == "0"


def test_map_fields_active_threats_with_count(test_sentinelone_device_asset_connector, sample_agent):
    """Test that active threats count is properly enriched with non-zero value."""
    # Arrange
    agent = sample_agent.model_copy(update={"activeThreats": 3})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    threats_enrichment = next((e for e in result.enrichments if e.name == "Active Threats"), None)
    assert threats_enrichment is not None
    assert threats_enrichment.value == "3"


def test_map_fields_infection_status_clean(test_sentinelone_device_asset_connector, sample_agent):
    """Test that infection status is properly enriched when clean."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    infection_enrichment = next((e for e in result.enrichments if e.name == "Infection Status"), None)
    assert infection_enrichment is not None
    assert infection_enrichment.value == "Clean"


def test_map_fields_infection_status_infected(test_sentinelone_device_asset_connector, sample_agent):
    """Test that infection status is properly enriched when infected."""
    # Arrange
    agent = sample_agent.model_copy(update={"infected": True})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    infection_enrichment = next((e for e in result.enrichments if e.name == "Infection Status"), None)
    assert infection_enrichment is not None
    assert infection_enrichment.value == "Infected"


def test_map_fields_no_threat_enrichments(test_sentinelone_device_asset_connector, sample_agent):
    """Test that no threat enrichments are added when data is None."""
    # Arrange
    agent = sample_agent.model_copy(update={"isUpToDate": None, "activeThreats": None, "infected": None})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    update_enrichment = next((e for e in result.enrichments if e.name == "Update Status"), None)
    threats_enrichment = next((e for e in result.enrichments if e.name == "Active Threats"), None)
    infection_enrichment = next((e for e in result.enrichments if e.name == "Infection Status"), None)

    assert update_enrichment is None
    assert threats_enrichment is None
    assert infection_enrichment is None
