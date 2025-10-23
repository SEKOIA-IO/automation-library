"""Unit tests for SentinelOneDeviceAssetConnector."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    Device,
    OperatingSystem,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.module import Module
from sentinelone_module.asset_connector.device_assets import SentinelOneDeviceAssetConnector
from sentinelone_module.asset_connector.models import (
    SentinelOneAgent,
    NetworkInterface,
    ActiveDirectory,
)


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
    with patch.object(type(connector), 'client', property(lambda self: mock_client)):
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
        osType="windows",
        totalMemory=8192,
        modelName="Acme computers - 15x4k",
        machineType="desktop",
        cpuId="Acme chips inc. Pro5555 @ 3.33GHz",
        cpuCount=2,
        coreCount=8,
        externalIp="31.155.5.7",
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
def test_get_device_os_windows(test_sentinelone_device_asset_connector):
    """Test OS mapping for Windows."""
    # Act
    os = test_sentinelone_device_asset_connector.get_device_os("windows", "Windows 10", "1909")

    # Assert
    assert os.name == "Windows 10 1909"
    assert os.type == OSTypeStr.WINDOWS
    assert os.type_id == OSTypeId.WINDOWS


def test_get_device_os_macos(test_sentinelone_device_asset_connector):
    """Test OS mapping for macOS."""
    # Act
    os = test_sentinelone_device_asset_connector.get_device_os("macos", "macOS Monterey", "12.0")

    # Assert
    assert os.name == "macOS Monterey 12.0"
    assert os.type == OSTypeStr.MACOS
    assert os.type_id == OSTypeId.MACOS


def test_get_device_os_linux(test_sentinelone_device_asset_connector):
    """Test OS mapping for Linux."""
    # Act
    os = test_sentinelone_device_asset_connector.get_device_os("linux", "Ubuntu", "20.04")

    # Assert
    assert os.name == "Ubuntu 20.04"
    assert os.type == OSTypeStr.LINUX
    assert os.type_id == OSTypeId.LINUX


def test_get_device_os_unknown(test_sentinelone_device_asset_connector):
    """Test OS mapping for unknown OS."""
    # Act
    os = test_sentinelone_device_asset_connector.get_device_os("unknown", "UnknownOS", "1.0")

    # Assert
    assert os.name == "UnknownOS 1.0"
    assert os.type == OSTypeStr.OTHER
    assert os.type_id == OSTypeId.OTHER


def test_get_device_os_none_values(test_sentinelone_device_asset_connector):
    """Test OS mapping with None values."""
    # Act
    os = test_sentinelone_device_asset_connector.get_device_os(None, None, None)

    # Assert
    assert os.name == "Unknown"
    assert os.type == OSTypeStr.OTHER
    assert os.type_id == OSTypeId.OTHER


# Tests for get_device_type method
def test_get_device_type_desktop(test_sentinelone_device_asset_connector):
    """Test device type mapping for desktop."""
    # Act
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type("desktop")

    # Assert
    assert device_type == DeviceTypeStr.DESKTOP
    assert device_id == DeviceTypeId.DESKTOP


def test_get_device_type_laptop(test_sentinelone_device_asset_connector):
    """Test device type mapping for laptop."""
    # Act
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type("laptop")

    # Assert
    assert device_type == DeviceTypeStr.LAPTOP
    assert device_id == DeviceTypeId.LAPTOP


def test_get_device_type_server(test_sentinelone_device_asset_connector):
    """Test device type mapping for server."""
    # Act
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type("server")

    # Assert
    assert device_type == DeviceTypeStr.SERVER
    assert device_id == DeviceTypeId.SERVER


def test_get_device_type_unknown(test_sentinelone_device_asset_connector):
    """Test device type mapping for unknown type."""
    # Act
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type("unknown")

    # Assert
    assert device_type == DeviceTypeStr.OTHER
    assert device_id == DeviceTypeId.OTHER


def test_get_device_type_none(test_sentinelone_device_asset_connector):
    """Test device type mapping with None."""
    # Act
    device_type, device_id = test_sentinelone_device_asset_connector.get_device_type(None)

    # Assert
    assert device_type == DeviceTypeStr.OTHER
    assert device_id == DeviceTypeId.OTHER


# Tests for map_fields method
def test_map_fields_success(test_sentinelone_device_asset_connector, sample_agent):
    """Test successful field mapping."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "JOHN-WIN-4125"
    assert result.device.uid == "ff819e70af13be381993075eb0ce5f2f6de05be2"
    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP
    assert result.device.os.name == "Windows 10 1909"
    assert result.device.os.type == OSTypeStr.WINDOWS
    assert result.activity_name == "Collect"
    assert result.category_name == "Discovery"
    assert result.class_name == "Device Inventory Info"
    assert result.metadata.product.name == "SentinelOne"
    assert result.metadata.product.vendor_name == "SentinelOne"
    assert result.metadata.product.version == "2.5.0.2417"
    assert result.severity == "Informational"


def test_map_fields_no_network_interface(test_sentinelone_device_asset_connector, sample_agent):
    """Test field mapping without network interface."""
    # Arrange
    sample_agent.networkInterfaces = None

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "JOHN-WIN-4125"
    assert result.device.uid == "ff819e70af13be381993075eb0ce5f2f6de05be2"


def test_map_fields_minimal_agent(test_sentinelone_device_asset_connector):
    """Test field mapping with minimal agent data."""
    # Arrange
    minimal_agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="MINIMAL-PC",
    )

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(minimal_agent)

    # Assert
    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "MINIMAL-PC"
    assert result.device.uid == "abc-def-ghi"
    assert result.device.type == DeviceTypeStr.OTHER
    assert result.device.os.type == OSTypeStr.OTHER


def test_map_fields_missing_id(test_sentinelone_device_asset_connector):
    """Test field mapping with missing ID raises ValueError."""
    # Arrange
    agent = SentinelOneAgent(
        id="",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc",
        computerName="TEST-PC",
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Agent ID is required"):
        test_sentinelone_device_asset_connector.map_fields(agent)


def test_map_fields_missing_computer_name(test_sentinelone_device_asset_connector):
    """Test field mapping with missing computer name raises ValueError."""
    # Arrange
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc",
        computerName=None,
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Computer name is required"):
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
