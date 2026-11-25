"""Unit tests for SentinelOneDeviceAssetConnector."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
    RiskLevelId,
    RiskLevelStr,
)
from sekoia_automation.module import Module

from sentinelone_module.asset_connector.device_assets import SentinelOneDeviceAssetConnector
from sentinelone_module.asset_connector.models import Location, NetworkInterface, SentinelOneAgent


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


def agent_created_at(sample_agent, created_at: str, name: str | None = None) -> SentinelOneAgent:
    agent = sample_agent.model_copy()
    agent.id = created_at
    agent.createdAt = created_at
    agent.computerName = name or f"PC-{created_at}"
    return agent


def page(agents: list[SentinelOneAgent], next_cursor: str | None = None) -> dict:
    return {"data": [a.model_dump() for a in agents], "errors": None, "pagination": {"nextCursor": next_cursor}}


# Tests for fetch_agents method
def test_fetch_agents_first_pass_page(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    connector._client_mock.get.return_value = page([sample_agent], "YWdlbnRfaWQ6NTgwMjkzODE=")

    agents, next_cursor = connector.fetch_agents(None)

    assert [a.id for a in agents] == [sample_agent.id]
    assert next_cursor == "YWdlbnRfaWQ6NTgwMjkzODE="
    connector._client_mock.get.assert_called_once_with(
        "/web/api/v2.1/agents", params={"limit": 100, "sortBy": "createdAt", "sortOrder": "asc"}
    )


def test_fetch_agents_resumes_after_checkpoint(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    connector._client_mock.get.return_value = page([sample_agent])

    connector.fetch_agents("2018-02-27T04:49:26.257525Z", "cursor1")

    connector._client_mock.get.assert_called_once_with(
        "/web/api/v2.1/agents",
        params={
            "limit": 100,
            "sortBy": "createdAt",
            "sortOrder": "asc",
            "createdAt__gt": "2018-02-27T04:49:26.257525Z",
            "cursor": "cursor1",
        },
    )


def test_fetch_agents_with_errors(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    connector._client_mock.get.return_value = {**page([sample_agent]), "errors": ["Some error occurred"]}

    agents, next_cursor = connector.fetch_agents(None)

    assert len(agents) == 1
    assert next_cursor is None
    connector.log.assert_any_call("Errors in API response: ['Some error occurred']", level="error")


def test_fetch_agents_empty_page_stops_pagination(test_sentinelone_device_asset_connector):
    connector = test_sentinelone_device_asset_connector
    connector._client_mock.get.return_value = {"data": [], "pagination": {"nextCursor": "cursor1"}}

    assert connector.fetch_agents(None) == ([], None)


def test_fetch_agents_exception_propagates(test_sentinelone_device_asset_connector):
    """A failed page must not end the pass as if every agent was fetched."""
    connector = test_sentinelone_device_asset_connector
    connector._client_mock.get.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        connector.fetch_agents(None)


def test_iter_agents_follows_pagination(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    first = agent_created_at(sample_agent, "2018-02-27T00:00:00.000000Z")
    second = agent_created_at(sample_agent, "2018-02-28T00:00:00.000000Z")

    with patch.object(connector, "fetch_agents", side_effect=[([first], "cursor1"), ([second], None)]) as fetch:
        agents = list(connector.iter_agents("checkpoint"))

    assert [a.id for a in agents] == [first.id, second.id]
    assert [c.args for c in fetch.call_args_list] == [("checkpoint", None), ("checkpoint", "cursor1")]


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
        ("laptop", DeviceTypeStr.DESKTOP, DeviceTypeId.DESKTOP),
        ("server", DeviceTypeStr.SERVER, DeviceTypeId.SERVER),
        ("tablet", DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE),
        ("mobile", DeviceTypeStr.MOBILE, DeviceTypeId.MOBILE),
        ("virtual", DeviceTypeStr.VIRTUAL, DeviceTypeId.VIRTUAL),
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
    assert result.device.name == "JOHN-WIN-4125"
    assert result.device.domain == "mybusiness.net"
    assert result.device.ip == "31.155.5.7"
    assert result.device.subnet == "31.155.5.x"
    assert result.device.model == "Acme computers - 15x4k"
    assert result.device.vendor_name is None
    assert result.device.is_managed is True
    assert result.device.is_compliant is True
    assert result.device.region == "Test Site"
    assert result.device.created_time is not None
    assert result.device.first_seen_time is not None
    assert result.device.last_seen_time is not None
    assert result.device.boot_time is not None
    assert result.device.uid_alt == "225494730938493804"

    # Org (from SentinelOne account)
    assert result.device.org is not None
    assert result.device.org.name == "Test Account"
    assert result.device.org.uid == "225494730938493804"

    # Risk level (sample agent has activeThreats=0 and infected=False → INFO)
    assert result.device.risk_level == RiskLevelStr.INFO
    assert result.device.risk_level_id == RiskLevelId.INFO
    assert result.device.risk_score == 0

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

    # Enrichments - all merged into single "Device Details" enrichment
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    details_enrichment = result.enrichments[0]
    assert details_enrichment.name == "Device Details"

    # Firewall enrichment
    assert "Firewall: Enabled" in details_enrichment.value
    assert details_enrichment.data.Firewall_status == "Enabled"

    # Domain enrichment
    assert "Domain: mybusiness.net" in details_enrichment.value
    assert details_enrichment.data.Full_qualified_domain_name == "mybusiness.net"

    # Users enrichment
    assert "janedoe3" in details_enrichment.value
    assert "john.doe" in details_enrichment.value
    assert details_enrichment.data.Users == ["janedoe3", "john.doe"]

    # Update Status enrichment
    assert "Update Status: Up to Date" in details_enrichment.value

    # Active Threats enrichment
    assert "Active Threats: 0" in details_enrichment.value

    # Infection Status enrichment
    assert "Infection Status: Clean" in details_enrichment.value


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
    assert result.device.eid is None

    # These fields should always be set
    assert result.device.name == "MINIMAL-PC"
    assert result.device.vendor_name is None
    assert result.device.is_managed is True
    assert result.device.created_time is not None

    # Risk level defaults to INFO when no threats and not infected
    assert result.device.risk_level == RiskLevelStr.INFO
    assert result.device.risk_level_id == RiskLevelId.INFO


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


@pytest.mark.parametrize(
    "infected,active_threats,expected_level,expected_id",
    [
        (True, 3, RiskLevelStr.CRITICAL, RiskLevelId.CRITICAL),
        (False, 5, RiskLevelStr.HIGH, RiskLevelId.HIGH),
        (False, 0, RiskLevelStr.INFO, RiskLevelId.INFO),
        (None, None, RiskLevelStr.INFO, RiskLevelId.INFO),
    ],
)
def test_map_fields_risk_level(
    test_sentinelone_device_asset_connector,
    infected,
    active_threats,
    expected_level,
    expected_id,
):
    """Test risk level derivation from infection state and active threats."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="456",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="RISK-PC",
        infected=infected,
        activeThreats=active_threats,
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.risk_level == expected_level
    assert result.device.risk_level_id == expected_id
    assert result.device.risk_score == active_threats


def test_map_fields_org_and_eid(test_sentinelone_device_asset_connector):
    """Test that org is built from account fields and eid from externalId."""
    agent = SentinelOneAgent(
        id="123",
        createdAt="2018-02-27T04:49:26.257525Z",
        updatedAt="2018-02-27T04:49:26.257525Z",
        accountId="acc-001",
        accountName="Acme Corp",
        siteId="789",
        uuid="abc-def-ghi",
        computerName="ORG-PC",
        externalId="ext-9999",
    )
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    assert result.device.org is not None
    assert result.device.org.name == "Acme Corp"
    assert result.device.org.uid == "acc-001"
    assert result.device.eid == "ext-9999"


# Tests for get_assets method
def test_get_assets_success(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    agents = [
        agent_created_at(sample_agent, "2018-02-27T00:00:00.000000Z", "JOHN-WIN-4125"),
        agent_created_at(sample_agent, "2018-02-28T00:00:00.000000Z", "JANE-MAC-5678"),
    ]

    with patch.object(connector, "iter_agents", return_value=iter(agents)) as iter_agents:
        assets = list(connector.get_assets())

    assert [a.device.hostname for a in assets] == ["JOHN-WIN-4125", "JANE-MAC-5678"]
    iter_agents.assert_called_once_with(None)


def test_get_assets_with_mapping_error(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    bad_agent = agent_created_at(sample_agent, "2018-02-27T00:00:00.000000Z")
    good_agent = agent_created_at(sample_agent, "2018-02-28T00:00:00.000000Z", "GOOD-PC")

    with (
        patch.object(connector, "iter_agents", return_value=iter([bad_agent, good_agent])),
        patch.object(connector, "map_fields", side_effect=[ValueError("bad agent"), connector.map_fields(good_agent)]),
    ):
        assets = list(connector.get_assets())

    assert [a.device.hostname for a in assets] == ["GOOD-PC"]
    connector.log.assert_any_call(f"Error while mapping agent {bad_agent.id}: bad agent", level="error")


def test_get_assets_empty_list(test_sentinelone_device_asset_connector):
    with patch.object(test_sentinelone_device_asset_connector, "iter_agents", return_value=iter([])):
        assert list(test_sentinelone_device_asset_connector.get_assets()) == []


# Tests for checkpoint management: one sweep pass over every agent per frequency
@pytest.fixture
def sweep_connector(test_sentinelone_device_asset_connector, sample_agent):
    connector = test_sentinelone_device_asset_connector
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
        "batch_size": 2,
    }
    connector.agents = [agent_created_at(sample_agent, f"2018-02-2{day}T00:00:00.000000Z") for day in (1, 2, 2, 3)]
    connector.checkpoints = []
    connector.pushed = []
    connector.fail_on_batch = None

    def iter_agents(checkpoint):
        connector.checkpoints.append(checkpoint)
        return iter([a for a in connector.agents if checkpoint is None or a.createdAt > checkpoint])

    def post(assets, asset_connector_api_url):
        connector.pushed.append([item.device.uid for item in assets.items])
        if len(connector.pushed) == connector.fail_on_batch:
            return None
        connector.update_checkpoint()
        return {}

    with (
        patch.object(connector, "iter_agents", side_effect=iter_agents),
        patch.object(connector, "post_assets_to_api", side_effect=post),
        patch("time.sleep"),
    ):
        yield connector


def stored(connector) -> dict:
    with connector.asset_checkpoint.store as store:
        return dict(store)


def test_sweep_pass_completes_then_waits_for_frequency(sweep_connector):
    with patch("time.time", return_value=1000.0):
        sweep_connector.asset_fetch_cycle()

    assert len(sum(sweep_connector.pushed, [])) == 4
    assert stored(sweep_connector) == {"cursor": None, "pass_started_at": 1000.0, "pass_completed": True}

    with patch("time.time", return_value=1030.0):
        sweep_connector.asset_fetch_cycle()

    assert sweep_connector.checkpoints == [None]

    with patch("time.time", return_value=1060.0):
        sweep_connector.asset_fetch_cycle()

    # Updated agents are refreshed: the next pass fetches every agent again.
    assert sweep_connector.checkpoints == [None, None]


def test_interrupted_pass_resumes_without_splitting_equal_dates(sweep_connector):
    sweep_connector.fail_on_batch = 2

    sweep_connector.asset_fetch_cycle()

    # The first batch ends inside the two agents created on the 22nd: only the 21st is safe.
    assert stored(sweep_connector)["cursor"] == "2018-02-21T00:00:00.000000Z"
    assert stored(sweep_connector)["pass_completed"] is False

    sweep_connector.asset_fetch_cycle()

    assert sweep_connector.checkpoints == [None, "2018-02-21T00:00:00.000000Z"]
    assert len(sweep_connector.pushed[-1] + sweep_connector.pushed[-2]) == 3
    assert stored(sweep_connector)["pass_completed"] is True


def test_unsorted_agents_freeze_the_checkpoint(sweep_connector, sample_agent):
    sweep_connector.agents = [
        agent_created_at(sample_agent, f"2018-02-2{day}T00:00:00.000000Z") for day in (1, 2, 4, 3)
    ]
    sweep_connector.fail_on_batch = 2

    sweep_connector.asset_fetch_cycle()

    assert stored(sweep_connector)["cursor"] == "2018-02-22T00:00:00.000000Z"
    sweep_connector.log.assert_any_call(
        "Agents are not sorted ascending on createdAt "
        "(2018-02-23T00:00:00.000000Z after 2018-02-24T00:00:00.000000Z). "
        "The checkpoint is not moved for the rest of this cycle",
        level="error",
    )


def test_reset_checkpoint_starts_a_new_pass(sweep_connector):
    sweep_connector.asset_fetch_cycle()

    sweep_connector.reset_checkpoint()

    assert stored(sweep_connector) == {}
    sweep_connector.asset_fetch_cycle()
    assert sweep_connector.checkpoints == [None, None]


def test_get_mapped_fields_is_empty(test_sentinelone_device_asset_connector):
    assert test_sentinelone_device_asset_connector.get_mapped_fields() == {}


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
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    if expected_enrichments:
        assert details_enrichment is not None
        assert f"Firewall: {expected_status}" in details_enrichment.value
        assert details_enrichment.data.Firewall_status == expected_status
    else:
        if details_enrichment:
            assert "Firewall:" not in details_enrichment.value


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
    # Verify it's a float timestamp
    assert isinstance(result.device.boot_time, float)
    # The expected timestamp for "2018-02-20T10:30:00.000000Z"
    from dateutil.parser import isoparse

    expected_timestamp = isoparse("2018-02-20T10:30:00.000000Z").timestamp()
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
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "janedoe3" in details_enrichment.value
    assert "john.doe" in details_enrichment.value
    assert len(details_enrichment.data.Users) == 2
    assert "janedoe3" in details_enrichment.data.Users
    assert "john.doe" in details_enrichment.data.Users


def test_map_fields_users_enrichment_no_duplicates(test_sentinelone_device_asset_connector, sample_agent):
    """Test that duplicate usernames are not included in enrichment."""
    # Arrange - set both usernames to the same value
    agent = sample_agent.model_copy(update={"lastLoggedInUserName": "john.doe", "osUsername": "john.doe"})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Users: john.doe" in details_enrichment.value
    assert len(details_enrichment.data.Users) == 1
    assert details_enrichment.data.Users[0] == "john.doe"


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
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Update Status: Up to Date" in details_enrichment.value


def test_map_fields_update_status_required(test_sentinelone_device_asset_connector, sample_agent):
    """Test that update required status is properly enriched."""
    # Arrange
    agent = sample_agent.model_copy(update={"isUpToDate": False})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Update Status: Update Required" in details_enrichment.value


def test_map_fields_active_threats_enrichment(test_sentinelone_device_asset_connector, sample_agent):
    """Test that active threats count is properly enriched."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Active Threats: 0" in details_enrichment.value


def test_map_fields_active_threats_with_count(test_sentinelone_device_asset_connector, sample_agent):
    """Test that active threats count is properly enriched with non-zero value."""
    # Arrange
    agent = sample_agent.model_copy(update={"activeThreats": 3})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Active Threats: 3" in details_enrichment.value


def test_map_fields_infection_status_clean(test_sentinelone_device_asset_connector, sample_agent):
    """Test that infection status is properly enriched when clean."""
    # Act
    result = test_sentinelone_device_asset_connector.map_fields(sample_agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Infection Status: Clean" in details_enrichment.value


def test_map_fields_infection_status_infected(test_sentinelone_device_asset_connector, sample_agent):
    """Test that infection status is properly enriched when infected."""
    # Arrange
    agent = sample_agent.model_copy(update={"infected": True})

    # Act
    result = test_sentinelone_device_asset_connector.map_fields(agent)

    # Assert
    details_enrichment = next((e for e in result.enrichments if e.name == "Device Details"), None)
    assert details_enrichment is not None
    assert "Infection Status: Infected" in details_enrichment.value


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
