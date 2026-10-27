from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from msgraph.generated.models.compliance_state import ComplianceState
from msgraph.generated.models.managed_device import ManagedDevice
from msgraph.generated.models.managed_device_owner_type import ManagedDeviceOwnerType
from msgraph.generated.models.management_agent_type import ManagementAgentType
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    NetworkInterfaceTypeId,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.module import Module

from asset_connector.device_assets import MicrosoftDefenderDeviceAssetConnector
from asset_connector.mappers import DeviceMapper, MissingHostnameError
from asset_connector.models import DefenderMachine


@pytest.fixture
def data_storage(tmp_path):
    return str(tmp_path)


@pytest.fixture
def connector(data_storage):
    module = Module()
    module.configuration = {
        "base_url": "https://api.securitycenter.microsoft.com",
        "app_id": "fake-app-id",
        "app_secret": "fake-app-secret",
        "tenant_id": "fake-tenant-id",
    }

    conn = MicrosoftDefenderDeviceAssetConnector(module=module, data_path=data_storage)
    conn.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake-api-key",
        "frequency": 60,
    }
    conn.log = Mock()
    conn.log_exception = Mock()
    return conn


@pytest.fixture
def sample_defender_machine():
    return DefenderMachine(
        id="1e5bc9d7e413ddd7902c2932e418702b84d0cc07",
        computerDnsName="mymachine1.contoso.com",
        firstSeen="2018-08-02T14:55:03.7791856Z",
        lastSeen="2024-12-01T10:00:00Z",
        osPlatform="Windows10",
        version="1709",
        osProcessor="x64",
        lastIpAddress="172.17.230.209",
        lastExternalIpAddress="203.0.113.10",
        osBuild=18209,
        healthStatus="Active",
        rbacGroupId=140,
        rbacGroupName="The-A-Team",
        riskScore="Low",
        exposureLevel="Medium",
        aadDeviceId="80fe8ff8-2624-418e-9591-41f0491218f9",
        machineTags=["test tag 1", "test tag 2"],
    )


@pytest.fixture
def sample_managed_device():
    device = ManagedDevice()
    device.id = "705c034c-034c-705c-4c03-5c704c035c70"
    device.device_name = "DESKTOP-ABC123"
    device.operating_system = "Windows"
    device.os_version = "10.0.22631.3880"
    device.model = "Surface Pro 9"
    device.manufacturer = "Microsoft Corporation"
    device.serial_number = "012345678901"
    device.imei = "353456789012345"
    device.wi_fi_mac_address = "AA:BB:CC:DD:EE:FF"
    device.ethernet_mac_address = "11:22:33:44:55:66"
    device.azure_a_d_device_id = "80fe8ff8-2624-418e-9591-41f0491218f9"
    device.user_principal_name = "user@contoso.com"
    device.management_agent = ManagementAgentType.Mdm
    device.compliance_state = ComplianceState.Compliant
    device.managed_device_owner_type = ManagedDeviceOwnerType.Company
    device.is_supervised = False
    device.enrolled_date_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    device.last_sync_date_time = datetime(2025, 4, 20, 14, 22, 0, tzinfo=timezone.utc)
    device.meid = None
    device.iccid = None
    device.udid = None
    return device


class TestResolveOsType:
    def test_windows(self):
        os_str, os_id = DeviceMapper.resolve_os_type("Windows10")
        assert os_str == OSTypeStr.WINDOWS
        assert os_id == OSTypeId.WINDOWS

    def test_linux(self):
        os_str, os_id = DeviceMapper.resolve_os_type("Linux")
        assert os_str == OSTypeStr.LINUX
        assert os_id == OSTypeId.LINUX

    def test_macos(self):
        os_str, os_id = DeviceMapper.resolve_os_type("macOS")
        assert os_str == OSTypeStr.MACOS
        assert os_id == OSTypeId.MACOS

    def test_android(self):
        os_str, os_id = DeviceMapper.resolve_os_type("Android")
        assert os_str == OSTypeStr.ANDROID
        assert os_id == OSTypeId.ANDROID

    def test_ios(self):
        os_str, os_id = DeviceMapper.resolve_os_type("iOS")
        assert os_str == OSTypeStr.IOS
        assert os_id == OSTypeId.IOS

    def test_unknown_os(self):
        os_str, os_id = DeviceMapper.resolve_os_type(None)
        assert os_str == OSTypeStr.UNKNOWN
        assert os_id == OSTypeId.UNKNOWN

    def test_other_os(self):
        os_str, os_id = DeviceMapper.resolve_os_type("ChromeOS")
        assert os_str == OSTypeStr.OTHER
        assert os_id == OSTypeId.OTHER


class TestResolveDeviceType:
    def test_desktop_for_windows(self):
        device_str, device_id = DeviceMapper.resolve_device_type(OSTypeStr.WINDOWS)
        assert device_str == DeviceTypeStr.DESKTOP
        assert device_id == DeviceTypeId.DESKTOP

    def test_mobile_for_android(self):
        device_str, device_id = DeviceMapper.resolve_device_type(OSTypeStr.ANDROID)
        assert device_str == DeviceTypeStr.MOBILE
        assert device_id == DeviceTypeId.MOBILE

    def test_mobile_for_ios(self):
        device_str, device_id = DeviceMapper.resolve_device_type(OSTypeStr.IOS)
        assert device_str == DeviceTypeStr.MOBILE
        assert device_id == DeviceTypeId.MOBILE


class TestResolveRiskLevel:
    def test_low(self):
        level_str, level_id = DeviceMapper.resolve_risk_level("Low")
        assert level_str == RiskLevelStr.LOW
        assert level_id == RiskLevelId.LOW

    def test_high(self):
        level_str, level_id = DeviceMapper.resolve_risk_level("High")
        assert level_str == RiskLevelStr.HIGH
        assert level_id == RiskLevelId.HIGH

    def test_none(self):
        level_str, level_id = DeviceMapper.resolve_risk_level(None)
        assert level_str is None
        assert level_id is None

    def test_unknown_value(self):
        level_str, level_id = DeviceMapper.resolve_risk_level("SuperDanger")
        assert level_str == RiskLevelStr.OTHER
        assert level_id == RiskLevelId.OTHER


class TestBuildDeviceFromMachine:
    def test_machine_only(self, sample_defender_machine):
        device = DeviceMapper(sample_defender_machine).build_device()

        assert device.uid == "1e5bc9d7e413ddd7902c2932e418702b84d0cc07"
        assert device.hostname == "mymachine1"
        assert device.domain == "contoso.com"
        assert device.type_id == DeviceTypeId.DESKTOP
        assert device.type == DeviceTypeStr.DESKTOP
        assert device.os.type == OSTypeStr.WINDOWS
        assert device.ip == "172.17.230.209"
        assert device.risk_level == RiskLevelStr.LOW
        assert device.risk_level_id == RiskLevelId.LOW
        assert device.is_managed is True
        assert device.first_seen_time is not None
        assert device.last_seen_time is not None
        # No managed device → no enriched fields
        assert device.network_interfaces is None

    def test_with_managed_device(self, sample_defender_machine, sample_managed_device):
        device = DeviceMapper(sample_defender_machine, sample_managed_device).build_device()

        assert device.uid == "1e5bc9d7e413ddd7902c2932e418702b84d0cc07"
        assert device.hostname == "mymachine1"
        assert device.domain == "contoso.com"
        assert device.model == "Surface Pro 9"
        assert device.vendor_name == "Microsoft Corporation"
        assert device.is_compliant is True
        assert device.is_personal is False
        assert device.is_supervised is False
        assert len(device.network_interfaces) == 2
        assert device.imei_list == ["353456789012345"]
        # OS version enriched from managed device
        assert device.os.name == "10.0.22631.3880"

    def test_minimal_machine(self):
        machine = DefenderMachine(id="minimal-id")
        with pytest.raises(MissingHostnameError, match="minimal-id"):
            DeviceMapper(machine).build_device()

    def test_minimal_machine_with_name(self):
        machine = DefenderMachine(id="minimal-id", computerDnsName="pc01")
        result = DeviceMapper(machine).build_device()
        assert result.uid == "minimal-id"
        assert result.hostname == "pc01"
        assert result.domain is None
        assert result.os.type == OSTypeStr.UNKNOWN
        assert result.network_interfaces is None

    def test_hostname_falls_back_to_intune_device_name(self, sample_managed_device):
        machine = DefenderMachine(id="no-dns-name", aadDeviceId="80fe8ff8-2624-418e-9591-41f0491218f9")
        sample_managed_device.device_name = "PC01"
        result = DeviceMapper(machine, sample_managed_device).build_device()
        assert result.hostname == "PC01"
        assert result.domain is None

    def test_intune_fallback_keeps_defender_domain(self, sample_managed_device):
        machine = DefenderMachine(id="short-dns-name", computerDnsName="a.corp.example.com")
        sample_managed_device.device_name = "PC01"
        result = DeviceMapper(machine, sample_managed_device).build_device()
        assert result.hostname == "PC01"
        assert result.domain == "corp.example.com"

    def test_unusable_intune_device_name_raises(self, sample_managed_device):
        machine = DefenderMachine(id="no-dns-name")
        sample_managed_device.device_name = "x"
        with pytest.raises(MissingHostnameError):
            DeviceMapper(machine, sample_managed_device).build_device()


class TestResolveHostname:
    @pytest.mark.parametrize(
        "computer_dns_name,expected",
        [
            ("pc01.corp.example.com", ("pc01", "corp.example.com")),
            ("mymachine1.contoso.com", ("mymachine1", "contoso.com")),
            ("shortname", ("shortname", None)),
            ("  padded.contoso.com  ", ("padded", "contoso.com")),
            ("trailingdot.", ("trailingdot", None)),
            ("ab.example.com", ("ab", "example.com")),
            (None, (None, None)),
            ("", (None, None)),
            ("   ", (None, None)),
            (".corp.example.com", (None, "corp.example.com")),
            ("a.example.com", (None, "example.com")),
        ],
    )
    def test_resolve_hostname(self, computer_dns_name, expected):
        assert DeviceMapper.resolve_hostname(computer_dns_name) == expected


class TestBuildEnrichments:
    def test_machine_only(self, sample_defender_machine):
        enrichments = DeviceMapper(sample_defender_machine).build_enrichments()
        names = [e.name for e in enrichments]
        assert "azure_ad_device_id" in names
        assert "health_status" in names
        assert "exposure_level" in names
        assert "rbac_group_name" in names

    def test_with_managed_device(self, sample_defender_machine, sample_managed_device):
        enrichments = DeviceMapper(sample_defender_machine, sample_managed_device).build_enrichments()
        names = [e.name for e in enrichments]
        assert "user_principal_name" in names
        assert "management_agent" in names

    def test_no_enrichments(self):
        machine = DefenderMachine(id="test")
        enrichments = DeviceMapper(machine).build_enrichments()
        assert enrichments is None


class TestDeviceMapperParts:
    def test_os_name_from_defender(self, sample_defender_machine):
        assert DeviceMapper(sample_defender_machine).build_os_name() == "Windows10 (Build 18209)"

    def test_os_name_prefers_intune_version(self, sample_defender_machine, sample_managed_device):
        assert DeviceMapper(sample_defender_machine, sample_managed_device).build_os_name() == "10.0.22631.3880"

    def test_network_interfaces_prefer_intune_macs(self, sample_defender_machine, sample_managed_device):
        interfaces = DeviceMapper(sample_defender_machine, sample_managed_device).build_network_interfaces()
        assert [(i.name, i.mac) for i in interfaces] == [
            ("ethernet", "11:22:33:44:55:66"),
            ("wifi", "AA:BB:CC:DD:EE:FF"),
        ]

    def test_network_interfaces_fall_back_on_defender_addresses(self):
        machine = DefenderMachine(
            id="m1",
            ipAddresses=[
                {"ipAddress": "10.0.0.5", "macAddress": "001122334455", "type": "Ethernet"},
                {"ipAddress": None, "macAddress": None, "type": "Wifi"},
            ],
        )
        interfaces = DeviceMapper(machine).build_network_interfaces()
        assert len(interfaces) == 1
        assert interfaces[0].ip == "10.0.0.5"
        assert interfaces[0].type_id == NetworkInterfaceTypeId.WIRED

    def test_no_network_interfaces(self):
        assert DeviceMapper(DefenderMachine(id="m1")).build_network_interfaces() is None

    def test_groups(self, sample_defender_machine):
        groups = DeviceMapper(sample_defender_machine).build_groups()
        assert [(g.name, g.uid) for g in groups] == [("The-A-Team", "140")]
        assert DeviceMapper(DefenderMachine(id="m1")).build_groups() is None

    def test_intune_flags(self, sample_defender_machine, sample_managed_device):
        mapper = DeviceMapper(sample_defender_machine, sample_managed_device)
        assert mapper.build_is_compliant() is True
        assert mapper.build_is_personal() is False
        without_intune = DeviceMapper(sample_defender_machine)
        assert without_intune.build_is_compliant() is None
        assert without_intune.build_is_personal() is None

    def test_event_time_uses_last_seen_then_first_seen(self):
        last_seen = DefenderMachine(id="m1", firstSeen="2020-01-01T00:00:00Z", lastSeen="2024-12-01T10:00:00Z")
        assert DeviceMapper(last_seen).build_event_time() == datetime(2024, 12, 1, 10, tzinfo=timezone.utc).timestamp()
        first_seen = DefenderMachine(id="m1", firstSeen="2020-01-01T00:00:00Z")
        assert DeviceMapper(first_seen).build_event_time() == datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()

    def test_event_time_defaults_to_now(self):
        before = datetime.now().timestamp()
        assert DeviceMapper(DefenderMachine(id="m1")).build_event_time() >= before

    def test_minimal_device(self, sample_defender_machine):
        device = DeviceMapper(sample_defender_machine).build_minimal_device()
        assert device.model_dump(exclude_none=True) == {
            "type_id": DeviceTypeId.DESKTOP,
            "type": DeviceTypeStr.DESKTOP,
            "uid": sample_defender_machine.id,
            "hostname": "mymachine1",
        }


class TestMapToOcsf:
    def test_produces_valid_ocsf_model(self, connector, sample_defender_machine, sample_managed_device):
        result = connector.map_to_ocsf(sample_defender_machine, sample_managed_device)

        assert isinstance(result, DeviceOCSFModel)
        assert result.class_uid == 5001
        assert result.type_uid == 500102
        assert result.activity_id == 2
        assert result.activity_name == "Collect"
        assert result.metadata.product.name == "Microsoft Defender for Endpoint"
        assert result.device.uid == sample_defender_machine.id

    def test_json_serializable(self, connector, sample_defender_machine):
        import json

        result = connector.map_to_ocsf(sample_defender_machine)
        json_data = result.model_dump()
        serialized = json.dumps(json_data)
        assert serialized
        assert json_data["class_uid"] == 5001


class TestFetchMachines:
    def test_single_page(self, connector, sample_defender_machine):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "value": [sample_defender_machine.dict()],
        }

        with patch.object(connector, "defender_client", create=True) as mock_client:
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=mock_response)
            machines = connector._fetch_machines()

        assert len(machines) == 1
        assert machines[0].id == sample_defender_machine.id

    def test_pagination(self, connector, sample_defender_machine):
        machine2 = DefenderMachine(id="second-machine-id", computerDnsName="machine2.contoso.com")

        mock_response_page1 = MagicMock()
        mock_response_page1.status_code = 200
        mock_response_page1.raise_for_status = Mock()
        mock_response_page1.json.return_value = {
            "value": [sample_defender_machine.dict()],
            "@odata.nextLink": "https://api.securitycenter.microsoft.com/api/machines?$skip=1",
        }

        mock_response_page2 = MagicMock()
        mock_response_page2.status_code = 200
        mock_response_page2.raise_for_status = Mock()
        mock_response_page2.json.return_value = {
            "value": [machine2.dict()],
        }

        with patch.object(connector, "defender_client", create=True) as mock_client:
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(side_effect=[mock_response_page1, mock_response_page2])
            machines = connector._fetch_machines()

        assert len(machines) == 2
        assert machines[0].id == sample_defender_machine.id
        assert machines[1].id == "second-machine-id"

    def test_api_error(self, connector):
        with patch.object(connector, "defender_client", create=True) as mock_client:
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(side_effect=Exception("API error"))
            with pytest.raises(Exception, match="API error"):
                connector._fetch_machines()

        connector.log.assert_called()

    def test_checkpoint_filter_applied(self, connector, sample_defender_machine):
        with connector.context as cache:
            cache["most_recent_date_seen"] = "2024-01-01T00:00:00+00:00"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [sample_defender_machine.dict()]}

        with patch.object(connector, "defender_client", create=True) as mock_client:
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=mock_response)
            connector._fetch_machines()
            called_url = mock_client.get.call_args[0][0]

        assert "%24filter=lastSeen+gt+2024-01-01T00%3A00%3A00%2B00%3A00" in called_url

    def test_no_filter_without_checkpoint(self, connector, sample_defender_machine):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [sample_defender_machine.dict()]}

        with patch.object(connector, "defender_client", create=True) as mock_client:
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=mock_response)
            connector._fetch_machines()
            called_url = mock_client.get.call_args[0][0]

        assert "%24filter" not in called_url
        assert "$filter" not in called_url


class TestFetchManagedDeviceByAadId:
    @pytest.mark.asyncio
    async def test_found(self, connector, sample_managed_device):
        mock_response = MagicMock()
        mock_response.value = [sample_managed_device]

        mock_managed_devices = MagicMock()
        mock_managed_devices.get = AsyncMock(return_value=mock_response)

        mock_device_management = MagicMock()
        mock_device_management.managed_devices = mock_managed_devices

        mock_client = MagicMock()
        mock_client.device_management = mock_device_management

        result = await connector._fetch_managed_device_by_aad_id(mock_client, "80fe8ff8-2624-418e-9591-41f0491218f9")

        assert result is not None
        assert result.id == sample_managed_device.id

    @pytest.mark.asyncio
    async def test_not_found(self, connector):
        mock_response = MagicMock()
        mock_response.value = []

        mock_managed_devices = MagicMock()
        mock_managed_devices.get = AsyncMock(return_value=mock_response)

        mock_device_management = MagicMock()
        mock_device_management.managed_devices = mock_managed_devices

        mock_client = MagicMock()
        mock_client.device_management = mock_device_management

        result = await connector._fetch_managed_device_by_aad_id(mock_client, "nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_api_error(self, connector):
        mock_managed_devices = MagicMock()
        mock_managed_devices.get = AsyncMock(side_effect=Exception("Graph error"))

        mock_device_management = MagicMock()
        mock_device_management.managed_devices = mock_managed_devices

        mock_client = MagicMock()
        mock_client.device_management = mock_device_management

        result = await connector._fetch_managed_device_by_aad_id(mock_client, "some-id")

        assert result is None
        connector.log.assert_called()


def _mock_graph_client(mock_client):
    """Helper: return an async context manager that yields mock_client."""

    @asynccontextmanager
    async def _fake_graph_client():
        yield mock_client

    return _fake_graph_client


class TestGetAssets:
    @pytest.mark.asyncio
    async def test_yields_ocsf_models(self, connector, sample_defender_machine, sample_managed_device):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [sample_defender_machine.dict()]}

        mock_graph_response = MagicMock()
        mock_graph_response.value = [sample_managed_device]

        mock_managed_devices = MagicMock()
        mock_managed_devices.get = AsyncMock(return_value=mock_graph_response)

        mock_device_management = MagicMock()
        mock_device_management.managed_devices = mock_managed_devices

        mock_graph_client = MagicMock()
        mock_graph_client.device_management = mock_device_management

        with patch.object(connector, "defender_client", create=True) as mock_def_client, patch.object(
            connector, "_graph_client", _mock_graph_client(mock_graph_client)
        ):
            mock_def_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_def_client.get = Mock(return_value=mock_response)
            assets = []
            async for asset in connector.get_assets():
                assets.append(asset)

        assert len(assets) == 1
        assert isinstance(assets[0], DeviceOCSFModel)
        assert assets[0].device.model == "Surface Pro 9"

    @pytest.mark.asyncio
    async def test_machine_without_aad_id(self, connector):
        machine = DefenderMachine(
            id="no-aad-machine",
            computerDnsName="noadd.contoso.com",
            osPlatform="Windows10",
            lastSeen="2024-12-01T10:00:00Z",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [machine.dict()]}

        mock_graph_client = MagicMock()

        with patch.object(connector, "defender_client", create=True) as mock_def_client, patch.object(
            connector, "_graph_client", _mock_graph_client(mock_graph_client)
        ):
            mock_def_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_def_client.get = Mock(return_value=mock_response)
            assets = []
            async for asset in connector.get_assets():
                assets.append(asset)

        assert len(assets) == 1
        # No graph call made, device still has basic info
        assert assets[0].device.uid == "no-aad-machine"
        assert assets[0].device.model is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("computer_dns_name", [None, "", "   ", ".corp.example.com", "a.example.com"])
    async def test_get_assets_skips_machine_without_usable_hostname(self, connector, computer_dns_name):
        nameless = DefenderMachine(
            id="nameless-machine",
            computerDnsName=computer_dns_name,
            osPlatform="Windows10",
            lastSeen="2024-12-02T10:00:00Z",
        )
        named = DefenderMachine(
            id="named-machine",
            computerDnsName="pc01.corp.example.com",
            osPlatform="Windows10",
            lastSeen="2024-12-01T10:00:00Z",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [nameless.dict(), named.dict()]}

        with patch.object(connector, "defender_client", create=True) as mock_def_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_def_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_def_client.get = Mock(return_value=mock_response)
            assets = []
            async for asset in connector.get_assets():
                assets.append(asset)

        assert len(assets) == 1
        assert assets[0].device.uid == "named-machine"
        assert all(len(asset.device.hostname) >= 2 for asset in assets)
        # The skipped machine still moves the cursor, so it is not re-fetched every cycle
        assert connector._latest_time_raw == "2024-12-02T10:00:00Z"


class TestUpdateCheckpoint:
    @pytest.mark.asyncio
    async def test_updates_context(self, connector):
        connector._latest_time_raw = "2025-04-20T14:22:00.123456Z"
        await connector.update_checkpoint()

        with connector.context as cache:
            assert cache["most_recent_date_seen"] == "2025-04-20T14:22:00.123456Z"

    @pytest.mark.asyncio
    async def test_preserves_seven_digit_precision(self, connector):
        # Defender timestamps can have 7 fractional digits (.NET 100-nanosecond precision).
        # Storing the raw string avoids truncation to microseconds which would make the
        # checkpoint slightly behind the real value and cause the last asset to pass the
        # `gt` filter again on the next run (duplication).
        raw = "2025-04-20T14:22:00.1234567Z"
        connector._latest_time_raw = raw
        await connector.update_checkpoint()

        with connector.context as cache:
            assert cache["most_recent_date_seen"] == raw

    @pytest.mark.asyncio
    async def test_no_update_when_no_latest(self, connector):
        connector._latest_time_raw = None
        await connector.update_checkpoint()

        with connector.context as cache:
            assert "most_recent_date_seen" not in cache


class TestGetAssetsCheckpointTracking:
    def _make_mock_response(self, machines: list):
        mock_response = MagicMock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"value": [m.dict() for m in machines]}
        return mock_response

    @pytest.mark.asyncio
    async def test_latest_time_raw_set_to_most_recent_last_seen(self, connector):
        machines = [
            DefenderMachine(id="a", lastSeen="2024-06-01T10:00:00.0000000Z"),
            DefenderMachine(id="b", lastSeen="2024-06-03T10:00:00.0000000Z"),
            DefenderMachine(id="c", lastSeen="2024-06-02T10:00:00.0000000Z"),
        ]

        with patch.object(connector, "defender_client", create=True) as mock_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=self._make_mock_response(machines))
            async for _ in connector.get_assets():
                pass

        assert connector._latest_time_raw == "2024-06-03T10:00:00.0000000Z"

    @pytest.mark.asyncio
    async def test_latest_time_raw_preserves_seven_digit_precision(self, connector):
        # Ensure the raw string with 7 fractional digits is kept verbatim.
        raw = "2024-12-01T10:00:00.1234567Z"
        machine = DefenderMachine(id="precise", lastSeen=raw)

        with patch.object(connector, "defender_client", create=True) as mock_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=self._make_mock_response([machine]))
            async for _ in connector.get_assets():
                pass

        assert connector._latest_time_raw == raw

    @pytest.mark.asyncio
    async def test_latest_time_raw_none_when_no_last_seen(self, connector):
        machine = DefenderMachine(id="no-date")

        with patch.object(connector, "defender_client", create=True) as mock_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=self._make_mock_response([machine]))
            async for _ in connector.get_assets():
                pass

        assert connector._latest_time_raw is None

    @pytest.mark.asyncio
    async def test_checkpoint_persisted_after_get_assets_and_update(self, connector):
        # Full cycle: get_assets sets _latest_time_raw, update_checkpoint persists it,
        # next _fetch_machines call uses it as filter.
        raw = "2024-12-01T10:00:00.1234567Z"
        machine = DefenderMachine(id="m1", lastSeen=raw)

        response = self._make_mock_response([machine])
        with patch.object(connector, "defender_client", create=True) as mock_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(return_value=response)
            async for _ in connector.get_assets():
                pass
            await connector.update_checkpoint()

        with connector.context as cache:
            assert cache["most_recent_date_seen"] == raw

    @pytest.mark.asyncio
    async def test_checkpoint_not_advanced_on_page_error(self, connector, sample_defender_machine):
        # A page error must stop the cycle: the cursor must not move past machines never fetched
        stored = "2024-01-01T00:00:00Z"
        with connector.context as cache:
            cache["most_recent_date_seen"] = stored

        page1 = MagicMock()
        page1.raise_for_status = Mock()
        page1.json.return_value = {
            "value": [sample_defender_machine.dict()],
            "@odata.nextLink": "https://api.securitycenter.microsoft.com/api/machines?$skip=1",
        }

        with patch.object(connector, "defender_client", create=True) as mock_client, patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ):
            mock_client.base_url = "https://api.securitycenter.microsoft.com"
            mock_client.get = Mock(side_effect=[page1, Exception("boom")])
            with pytest.raises(Exception, match="boom"):
                async for _ in connector.get_assets():
                    pass
            await connector.update_checkpoint()

        assert connector._latest_time_raw is None
        with connector.context as cache:
            assert cache["most_recent_date_seen"] == stored

    @pytest.mark.asyncio
    async def test_checkpoint_not_advanced_when_stopped(self, connector):
        machine = DefenderMachine(id="m1", computerDnsName="pc01.corp.example.com", lastSeen="2024-12-01T10:00:00Z")

        with patch.object(connector, "_fetch_machines", return_value=[machine]), patch.object(
            connector, "_graph_client", _mock_graph_client(MagicMock())
        ), patch.object(type(connector), "running", new_callable=PropertyMock, return_value=False):
            assets = [asset async for asset in connector.get_assets()]

        assert assets == []
        assert connector._latest_time_raw is None
