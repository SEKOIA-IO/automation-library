"""
Unit tests for SophosDeviceAssetConnector (asset_connector/device_assets.py).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests_mock as req_mock

from sophos_module.base import SophosModule
from sophos_module.asset_connector.device_assets import SophosDeviceAssetConnector
from sophos_module.asset_connector.model import (
    SophosEndpoint,
    SophosEndpointsResponse,
    SophosHealth,
    SophosOS,
    SophosTenant,
    SophosCloud,
    SophosIsolation,
    SophosAssociatedPerson,
    SophosPages,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)

COMPUTER_ENDPOINT = SophosEndpoint(
    id="aaaaaaaa-0000-0000-0000-000000000001",
    type="computer",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    hostname="test-computer-01",
    health=SophosHealth(overall="bad"),
    os=SophosOS(
        isServer=False, platform="windows", name="Windows 10 Pro", majorVersion=10, minorVersion=0, build=19044
    ),
    ipv4Addresses=["192.0.2.1"],
    ipv6Addresses=[],
    macAddresses=["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"],
    tamperProtectionEnabled=True,
    associatedPerson=SophosAssociatedPerson(
        name="test-computer-01\\testuser",
        viaLogin="test-computer-01\\testuser",
        id="cccccccc-0000-0000-0000-000000000001",
    ),
    lastSeenAt="2024-01-07T06:26:08.668Z",
    registeredAt="2023-06-26T10:28:08.836Z",
    cloud=SophosCloud(provider="azure", instanceId="dddddddd-0000-0000-0000-000000000001"),
    isolation=SophosIsolation(status="notIsolated", adminIsolated=False, selfIsolated=False),
    online=False,
    tags=[],
)

SERVER_ENDPOINT = SophosEndpoint(
    id="aaaaaaaa-0000-0000-0000-000000000002",
    type="server",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    hostname="test-server-01",
    health=SophosHealth(overall="good"),
    os=SophosOS(isServer=True, platform="linux", name="Ubuntu 22.04 LTS"),
    ipv4Addresses=["192.0.2.2"],
    ipv6Addresses=["fe80::1"],
    macAddresses=["AA:BB:CC:DD:EE:03"],
    tamperProtectionEnabled=False,
    associatedPerson=SophosAssociatedPerson(),
    lastSeenAt="2025-01-06T11:24:27.741Z",
    registeredAt="2024-09-30T07:13:25.289Z",
    online=False,
    tags=[],
)

MINIMAL_ENDPOINT = SophosEndpoint(
    id="aaaaaaaa-0000-0000-0000-000000000003",
    type="computer",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000002"),
    hostname="test-minimal-01",
    health=SophosHealth(overall="good"),
    os=SophosOS(platform="macos", name="macOS 14"),
    ipv4Addresses=[],
    macAddresses=[],
    tamperProtectionEnabled=None,
    associatedPerson=SophosAssociatedPerson(),
    lastSeenAt=None,
    registeredAt=None,
    online=True,
    tags=[],
)

# Raw dict versions for HTTP mock tests
COMPUTER_ENDPOINT_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "type": "computer",
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "hostname": "test-computer-01",
    "health": {"overall": "bad", "threats": {"status": "good"}, "services": {"status": "bad"}},
    "os": {
        "isServer": False,
        "platform": "windows",
        "name": "Windows 10 Pro",
        "majorVersion": 10,
        "minorVersion": 0,
        "build": 19044,
    },
    "ipv4Addresses": ["192.0.2.1"],
    "ipv6Addresses": [],
    "macAddresses": ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"],
    "tamperProtectionEnabled": True,
    "associatedPerson": {
        "name": "test-computer-01\\testuser",
        "viaLogin": "test-computer-01\\testuser",
        "id": "cccccccc-0000-0000-0000-000000000001",
    },
    "lastSeenAt": "2024-01-07T06:26:08.668Z",
    "registeredAt": "2023-06-26T10:28:08.836Z",
    "cloud": {"provider": "azure", "instanceId": "dddddddd-0000-0000-0000-000000000001"},
    "isolation": {"status": "notIsolated", "adminIsolated": False, "selfIsolated": False},
    "online": False,
    "tags": [],
}

SERVER_ENDPOINT_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000002",
    "type": "server",
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "hostname": "test-server-01",
    "health": {"overall": "good", "threats": {"status": "good"}, "services": {"status": "good"}},
    "os": {"isServer": True, "platform": "linux", "name": "Ubuntu 22.04 LTS"},
    "ipv4Addresses": ["192.0.2.2"],
    "ipv6Addresses": ["fe80::1"],
    "macAddresses": ["AA:BB:CC:DD:EE:03"],
    "tamperProtectionEnabled": False,
    "associatedPerson": {},
    "lastSeenAt": "2025-01-06T11:24:27.741Z",
    "registeredAt": "2024-09-30T07:13:25.289Z",
    "online": False,
    "tags": [],
}

API_RESPONSE_PAGE1 = {
    "items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT],
    "pages": {"size": 50, "maxSize": 500, "nextKey": "page2key"},
}

API_RESPONSE_PAGE2 = {
    "items": [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000003",
            "type": "computer",
            "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000002"},
            "hostname": "test-minimal-01",
            "health": {"overall": "good"},
            "os": {"platform": "macos", "name": "macOS 14"},
            "ipv4Addresses": [],
            "macAddresses": [],
            "online": True,
            "tags": [],
        }
    ],
    "pages": {"size": 50, "maxSize": 500},
}

AUTH_TOKEN_RESPONSE = {
    "access_token": "test_access_token",
    "refresh_token": "test_refresh_token",
    "token_type": "bearer",
    "message": "OK",
    "errorCode": "success",
    "expires_in": 3600,
}

WHOAMI_RESPONSE = {
    "id": "bbbbbbbb-0000-0000-0000-000000000001",
    "idType": "tenant",
    "apiHosts": {
        "global": "https://api.central.sophos.com",
        "dataRegion": "https://api-eu01.central.sophos.com",
    },
}

AUTH_URL = "https://id.sophos.com/api/v2/oauth2/token"


@pytest.fixture
def connector(symphony_storage):
    module = SophosModule()
    c = SophosDeviceAssetConnector(module=module, data_path=symphony_storage)
    c.module.configuration = {
        "oauth2_authorization_url": AUTH_URL,
        "api_host": "https://api.central.sophos.com",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }
    c.log = MagicMock()
    c.log_exception = MagicMock()
    type(c).running = property(lambda self: True)
    return c


class TestGetOs:
    def test_windows(self, connector):
        os_obj = connector._get_os(COMPUTER_ENDPOINT)
        assert os_obj.type_id == OSTypeId.WINDOWS
        assert os_obj.type == OSTypeStr.WINDOWS
        assert os_obj.name == "Windows 10 Pro"

    def test_linux(self, connector):
        os_obj = connector._get_os(SERVER_ENDPOINT)
        assert os_obj.type_id == OSTypeId.LINUX
        assert os_obj.type == OSTypeStr.LINUX

    def test_macos(self, connector):
        ep = SophosEndpoint(id="x", hostname="h", os=SophosOS(platform="macos", name="macOS 14"))
        os_obj = connector._get_os(ep)
        assert os_obj.type_id == OSTypeId.MACOS

    def test_android(self, connector):
        ep = SophosEndpoint(id="x", hostname="h", os=SophosOS(platform="android", name="Android 13"))
        os_obj = connector._get_os(ep)
        assert os_obj.type_id == OSTypeId.ANDROID

    def test_unknown_platform(self, connector):
        ep = SophosEndpoint(id="x", hostname="h", os=SophosOS(platform="exotic", name="Exotic OS"))
        os_obj = connector._get_os(ep)
        assert os_obj.type_id == OSTypeId.UNKNOWN

    def test_missing_os_key(self, connector):
        ep = SophosEndpoint(id="x", hostname="h")
        os_obj = connector._get_os(ep)
        assert os_obj.type_id == OSTypeId.UNKNOWN


class TestGetDeviceType:
    def test_computer(self):
        type_id, type_str = SophosDeviceAssetConnector._get_device_type(COMPUTER_ENDPOINT)
        assert type_id == DeviceTypeId.DESKTOP
        assert type_str == DeviceTypeStr.DESKTOP

    def test_server(self):
        type_id, type_str = SophosDeviceAssetConnector._get_device_type(SERVER_ENDPOINT)
        assert type_id == DeviceTypeId.SERVER
        assert type_str == DeviceTypeStr.SERVER

    def test_unknown(self):
        ep = SophosEndpoint(id="x", hostname="h", type="tablet")
        type_id, type_str = SophosDeviceAssetConnector._get_device_type(ep)
        assert type_id == DeviceTypeId.UNKNOWN

    def test_missing_key(self):
        ep = SophosEndpoint(id="x", hostname="h")
        type_id, _ = SophosDeviceAssetConnector._get_device_type(ep)
        assert type_id == DeviceTypeId.UNKNOWN


class TestGetNetworkInterfaces:
    def test_single_ipv4_with_mac(self):
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(COMPUTER_ENDPOINT)
        assert interfaces is not None
        assert len(interfaces) == 1
        iface = interfaces[0]
        assert iface.ip == "192.0.2.1"
        assert iface.mac == "AA:BB:CC:DD:EE:01"
        assert iface.hostname == "test-computer-01"
        assert iface.name == "eth0"

    def test_ipv4_and_ipv6(self):
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(SERVER_ENDPOINT)
        assert interfaces is not None
        assert len(interfaces) == 2
        assert interfaces[0].ip == "192.0.2.2"
        assert interfaces[1].ip == "fe80::1"

    def test_no_addresses_returns_none(self):
        ep = SophosEndpoint(id="x", hostname="h", ipv4Addresses=[], ipv6Addresses=[], macAddresses=[])
        result = SophosDeviceAssetConnector._get_network_interfaces(ep)
        assert result is None

    def test_mac_normalization(self):
        ep = SophosEndpoint(
            id="x",
            hostname="h",
            ipv4Addresses=["192.0.2.10"],
            ipv6Addresses=[],
            macAddresses=["aa-bb-cc-dd-ee-ff"],
        )
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(ep)
        assert interfaces is not None
        assert interfaces[0].mac == "AA:BB:CC:DD:EE:FF"

    def test_hostname_only_on_first_interface(self):
        ep = SophosEndpoint(
            id="x",
            hostname="myhost",
            ipv4Addresses=["192.0.2.1", "192.0.2.2"],
            ipv6Addresses=[],
            macAddresses=["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"],
        )
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(ep)
        assert interfaces is not None
        assert interfaces[0].hostname == "myhost"
        assert interfaces[1].hostname is None


class TestNormalizeMac:
    def test_dashes_to_colons(self):
        assert SophosDeviceAssetConnector._normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"

    def test_already_correct(self):
        assert SophosDeviceAssetConnector._normalize_mac("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"

    def test_none_input(self):
        assert SophosDeviceAssetConnector._normalize_mac(None) is None

    def test_empty_string(self):
        assert SophosDeviceAssetConnector._normalize_mac("") is None


class TestIsCompliant:
    def test_good(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="good"))
        assert SophosDeviceAssetConnector._is_compliant(ep) is True

    def test_bad(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="bad"))
        assert SophosDeviceAssetConnector._is_compliant(ep) is False

    def test_suspicious(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="suspicious"))
        assert SophosDeviceAssetConnector._is_compliant(ep) is False

    def test_unknown_value(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="unknown"))
        assert SophosDeviceAssetConnector._is_compliant(ep) is None

    def test_missing_health(self):
        ep = SophosEndpoint(id="x", hostname="h")
        assert SophosDeviceAssetConnector._is_compliant(ep) is None


class TestGetFirewallStatus:
    def test_enabled(self):
        ep = SophosEndpoint(id="x", hostname="h", tamperProtectionEnabled=True)
        assert SophosDeviceAssetConnector._get_firewall_status(ep) == "Enabled"

    def test_disabled(self):
        ep = SophosEndpoint(id="x", hostname="h", tamperProtectionEnabled=False)
        assert SophosDeviceAssetConnector._get_firewall_status(ep) == "Disabled"

    def test_none_value(self):
        ep = SophosEndpoint(id="x", hostname="h", tamperProtectionEnabled=None)
        assert SophosDeviceAssetConnector._get_firewall_status(ep) is None

    def test_missing_key(self):
        ep = SophosEndpoint(id="x", hostname="h")
        assert SophosDeviceAssetConnector._get_firewall_status(ep) is None


class TestGetOrganization:
    def test_tenant_present(self):
        org = SophosDeviceAssetConnector._get_organization(COMPUTER_ENDPOINT)
        assert org is not None
        assert org.uid == "bbbbbbbb-0000-0000-0000-000000000001"

    def test_tenant_missing(self):
        ep = SophosEndpoint(id="x", hostname="h")
        assert SophosDeviceAssetConnector._get_organization(ep) is None

    def test_tenant_empty_id(self):
        ep = SophosEndpoint(id="x", hostname="h", tenant=SophosTenant(id=""))
        assert SophosDeviceAssetConnector._get_organization(ep) is None


class TestParseTs:
    def test_valid_iso(self):
        ts = SophosDeviceAssetConnector._parse_ts("2024-01-07T06:26:08.668Z")
        assert isinstance(ts, float)
        assert ts > 0

    def test_none_input(self):
        assert SophosDeviceAssetConnector._parse_ts(None) is None

    def test_empty_string(self):
        assert SophosDeviceAssetConnector._parse_ts("") is None

    def test_invalid_string(self):
        assert SophosDeviceAssetConnector._parse_ts("not-a-date") is None


class TestMapDeviceFields:
    def test_computer_mapping(self, connector):
        result = connector.map_device_fields(COMPUTER_ENDPOINT)
        assert result is not None
        assert result.device.uid == "aaaaaaaa-0000-0000-0000-000000000001"
        assert result.device.hostname == "test-computer-01"
        assert result.device.type_id == DeviceTypeId.DESKTOP
        assert result.device.os.type_id == OSTypeId.WINDOWS
        assert result.device.ip == "192.0.2.1"
        assert result.device.is_compliant is False
        assert result.device.is_managed is True
        assert result.device.region == "azure"
        assert result.device.desc == "test-computer-01\\testuser"
        assert result.activity_id == 2
        assert result.class_uid == 5001
        assert result.type_uid == 500102

    def test_server_mapping(self, connector):
        result = connector.map_device_fields(SERVER_ENDPOINT)
        assert result is not None
        assert result.device.type_id == DeviceTypeId.SERVER
        assert result.device.os.type_id == OSTypeId.LINUX
        assert result.device.is_compliant is True

    def test_missing_id_returns_none(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"id": None})
        assert connector.map_device_fields(ep) is None
        connector.log.assert_called()

    def test_missing_hostname_returns_none(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"hostname": None})
        assert connector.map_device_fields(ep) is None

    def test_no_cloud_field(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"cloud": None})
        result = connector.map_device_fields(ep)
        assert result is not None
        assert result.device.region is None

    def test_no_associated_person(self, connector):
        result = connector.map_device_fields(SERVER_ENDPOINT)
        assert result is not None
        assert result.device.desc is None

    def test_enrichments_present(self, connector):
        result = connector.map_device_fields(COMPUTER_ENDPOINT)
        assert result is not None
        assert result.enrichments is not None
        assert len(result.enrichments) == 1
        assert result.enrichments[0].name == "compliance"

    def test_metadata_product_name(self, connector):
        result = connector.map_device_fields(COMPUTER_ENDPOINT)
        assert result is not None
        assert result.metadata.product.name == "Sophos EDR"

    def test_timestamps(self, connector):
        result = connector.map_device_fields(COMPUTER_ENDPOINT)
        assert result is not None
        assert result.device.last_seen_time is not None
        assert result.device.first_seen_time is not None


class TestIterEndpoints:
    def test_single_page(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        items = list(connector._iter_endpoints())
        assert len(items) == 2
        connector.client.list_endpoints.assert_called_once()

    def test_pagination(self, connector):
        mock_resp_1 = MagicMock()
        mock_resp_1.raise_for_status = MagicMock()
        mock_resp_1.json.return_value = API_RESPONSE_PAGE1

        mock_resp_2 = MagicMock()
        mock_resp_2.raise_for_status = MagicMock()
        mock_resp_2.json.return_value = API_RESPONSE_PAGE2

        connector.client = MagicMock()
        connector.client.list_endpoints.side_effect = [mock_resp_1, mock_resp_2]

        items = list(connector._iter_endpoints())
        assert len(items) == 3
        assert connector.client.list_endpoints.call_count == 2
        second_params = connector.client.list_endpoints.call_args_list[1][0][0]
        assert second_params.get("pageFromKey") == "page2key"

    def test_stops_when_not_running(self, connector):
        type(connector).running = property(lambda self: False)
        connector.client = MagicMock()
        assert list(connector._iter_endpoints()) == []
        connector.client.list_endpoints.assert_not_called()

    def test_empty_items(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"items": [], "pages": {"size": 50, "maxSize": 500}}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        assert list(connector._iter_endpoints()) == []


class TestUpdateCheckpoint:
    def test_writes_latest_time(self, connector):
        connector._latest_time = "2025-01-01T00:00:00.000Z"
        connector.update_checkpoint()
        with connector.context as cache:
            assert cache.get("last_seen_cursor") == "2025-01-01T00:00:00.000Z"

    def test_no_update_when_no_latest_time(self, connector):
        connector._latest_time = None
        connector.update_checkpoint()
        with connector.context as cache:
            assert cache.get("last_seen_cursor") is None


class TestGetAssets:
    def test_yields_valid_models(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        assets = list(connector.get_assets())
        assert len(assets) == 2

    def test_skips_invalid_endpoints(self, connector):
        no_id = {**COMPUTER_ENDPOINT_DICT, "id": None}
        no_hostname = {**SERVER_ENDPOINT_DICT, "hostname": ""}
        minimal = {
            "id": "aaaaaaaa-0000-0000-0000-000000000003",
            "type": "computer",
            "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000002"},
            "hostname": "test-minimal-01",
            "health": {"overall": "good"},
            "os": {"platform": "macos"},
            "ipv4Addresses": [],
            "macAddresses": [],
            "online": True,
            "tags": [],
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "items": [no_id, no_hostname, minimal],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        assets = list(connector.get_assets())
        assert len(assets) == 1

    def test_raises_on_http_error(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        with pytest.raises(Exception, match="HTTP 500"):
            list(connector.get_assets())

    def test_update_checkpoint_noop_when_no_data(self, connector):
        connector.update_checkpoint()  # must not raise


class TestFullHttpRoundTrip:
    def test_collect_endpoints_via_http(self, connector):
        data_region = "https://api-eu01.central.sophos.com"

        with req_mock.Mocker() as m:
            m.post(AUTH_URL, json=AUTH_TOKEN_RESPONSE, status_code=200)
            m.get("https://api.central.sophos.com/whoami/v1", json=WHOAMI_RESPONSE, status_code=200)
            m.get(
                f"{data_region}/endpoint/v1/endpoints",
                json={"items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT], "pages": {"size": 50, "maxSize": 500}},
                status_code=200,
            )

            if "client" in connector.__dict__:
                del connector.__dict__["client"]

            assets = list(connector.get_assets())

        assert len(assets) == 2
        hostnames = {a.device.hostname for a in assets}
        assert "test-computer-01" in hostnames
        assert "test-server-01" in hostnames


def _make_response(connector, items, next_key=None):
    """Helper to build a mocked API response."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    pages = {"size": 50, "maxSize": 500}
    if next_key:
        pages["nextKey"] = next_key
    mock_resp.json.return_value = {"items": items, "pages": pages}
    connector.client = MagicMock()
    connector.client.list_endpoints.return_value = mock_resp
    return mock_resp


class TestLoadSentIds:
    def _entry(self, fp="abc", days_ago=0):
        ts = (datetime.now(tz=timezone.utc) - timedelta(days=days_ago)).isoformat()
        return {"fingerprint": fp, "cached_at": ts}

    def test_empty_context_gives_empty_cache(self, connector):
        connector._load_sent_ids()
        assert connector._sent_ids == {}

    def test_loads_recent_ids(self, connector):
        with connector.context as cache:
            cache["sent_ids"] = {
                "id-1": self._entry("fp1"),
                "id-2": self._entry("fp2"),
            }
        connector._load_sent_ids()
        assert "id-1" in connector._sent_ids
        assert "id-2" in connector._sent_ids

    def test_prunes_old_ids(self, connector):
        with connector.context as cache:
            cache["sent_ids"] = {
                "old-id": self._entry("old", days_ago=10),
                "new-id": self._entry("new", days_ago=0),
            }
        connector._load_sent_ids()
        assert "old-id" not in connector._sent_ids
        assert "new-id" in connector._sent_ids

    def test_enforces_max_cache_size(self, connector):
        connector.MAX_CACHE_SIZE = 3
        recent_base = datetime.now(tz=timezone.utc)
        entries = {
            f"id-{i}": {
                "fingerprint": f"fp-{i}",
                "cached_at": (recent_base - timedelta(minutes=i)).isoformat(),
            }
            for i in range(10)
        }
        with connector.context as cache:
            cache["sent_ids"] = entries
        connector._load_sent_ids()
        assert len(connector._sent_ids) == 3
        assert "id-0" in connector._sent_ids
        assert "id-1" in connector._sent_ids
        assert "id-2" in connector._sent_ids

    def test_entry_at_exact_boundary_is_kept(self, connector):
        """Entry exactly at CACHE_MAX_AGE_DAYS old should still be kept (>= cutoff)."""
        boundary = (
            datetime.now(tz=timezone.utc) - timedelta(days=connector.CACHE_MAX_AGE_DAYS, seconds=-1)
        ).isoformat()
        with connector.context as cache:
            cache["sent_ids"] = {"boundary-id": {"fingerprint": "fp", "cached_at": boundary}}
        connector._load_sent_ids()
        assert "boundary-id" in connector._sent_ids

    def test_log_eviction_count(self, connector):
        """Debug log must report the correct number of evicted entries."""
        old = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()
        recent = datetime.now(tz=timezone.utc).isoformat()
        with connector.context as cache:
            cache["sent_ids"] = {
                "old-1": {"fingerprint": "fp1", "cached_at": old},
                "old-2": {"fingerprint": "fp2", "cached_at": old},
                "new-1": {"fingerprint": "fp3", "cached_at": recent},
            }
        connector._load_sent_ids()
        log_calls = [str(call) for call in connector.log.call_args_list]
        assert any("evicted=2" in call for call in log_calls)


class TestSaveSentIds:
    def test_persists_to_context(self, connector):
        recent = datetime.now(tz=timezone.utc).isoformat()
        connector._sent_ids = {"id-1": {"fingerprint": "fp1", "cached_at": recent}}
        connector._save_sent_ids()
        with connector.context as cache:
            entry = cache.get("sent_ids", {}).get("id-1")
        assert entry is not None
        assert entry["fingerprint"] == "fp1"


class TestComputeFingerprint:
    def test_same_endpoint_same_fingerprint(self):
        fp1 = SophosDeviceAssetConnector._compute_fingerprint(COMPUTER_ENDPOINT)
        fp2 = SophosDeviceAssetConnector._compute_fingerprint(COMPUTER_ENDPOINT)
        assert fp1 == fp2

    def test_different_endpoints_different_fingerprint(self):
        fp1 = SophosDeviceAssetConnector._compute_fingerprint(COMPUTER_ENDPOINT)
        fp2 = SophosDeviceAssetConnector._compute_fingerprint(SERVER_ENDPOINT)
        assert fp1 != fp2

    def test_last_seen_at_change_does_not_change_fingerprint(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"lastSeenAt": "2026-01-01T00:00:00.000Z"})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"lastSeenAt": "2026-06-01T12:00:00.000Z"})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) == SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_registered_at_change_does_not_change_fingerprint(self):
        """registeredAt is excluded; changing it must not affect the fingerprint."""
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"registeredAt": "2023-01-01T00:00:00.000Z"})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"registeredAt": "2025-01-01T00:00:00.000Z"})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) == SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_hostname_change_changes_fingerprint(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"hostname": "host-a"})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"hostname": "host-b"})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_health_change_changes_fingerprint(self):
        ep_good = COMPUTER_ENDPOINT.model_copy(update={"health": SophosHealth(overall="good")})
        ep_bad = COMPUTER_ENDPOINT.model_copy(update={"health": SophosHealth(overall="bad")})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_good
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_bad)

    def test_ip_change_changes_fingerprint(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"ipv4Addresses": ["192.0.2.1"]})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"ipv4Addresses": ["10.0.0.1"]})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_ip_order_does_not_matter(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"ipv4Addresses": ["10.0.0.1", "10.0.0.2"]})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"ipv4Addresses": ["10.0.0.2", "10.0.0.1"]})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) == SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_mac_order_does_not_matter(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"macAddresses": ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"macAddresses": ["AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:01"]})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) == SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_tamper_protection_change_changes_fingerprint(self):
        ep_on = COMPUTER_ENDPOINT.model_copy(update={"tamperProtectionEnabled": True})
        ep_off = COMPUTER_ENDPOINT.model_copy(update={"tamperProtectionEnabled": False})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_on
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_off)

    def test_isolation_status_change_changes_fingerprint(self):
        ep_free = COMPUTER_ENDPOINT.model_copy(update={"isolation": SophosIsolation(status="notIsolated")})
        ep_isolated = COMPUTER_ENDPOINT.model_copy(update={"isolation": SophosIsolation(status="isolated")})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_free
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_isolated)

    def test_os_change_changes_fingerprint(self):
        ep_a = COMPUTER_ENDPOINT.model_copy(update={"os": SophosOS(platform="windows", name="Windows 10")})
        ep_b = COMPUTER_ENDPOINT.model_copy(update={"os": SophosOS(platform="windows", name="Windows 11")})
        assert SophosDeviceAssetConnector._compute_fingerprint(
            ep_a
        ) != SophosDeviceAssetConnector._compute_fingerprint(ep_b)

    def test_none_optional_fields_do_not_crash(self):
        """Fingerprint must work cleanly when optional fields are absent."""
        ep = SophosEndpoint(id="x", hostname="h")
        fp = SophosDeviceAssetConnector._compute_fingerprint(ep)
        assert isinstance(fp, str) and len(fp) == 64  # SHA-256 hex = 64 chars

    def test_returns_sha256_hex_string(self):
        fp = SophosDeviceAssetConnector._compute_fingerprint(COMPUTER_ENDPOINT)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestGetGroups:
    def test_valid_group_returned(self, connector):
        from sophos_module.asset_connector.model import SophosGroup

        ep = COMPUTER_ENDPOINT.model_copy(update={"group": SophosGroup(id="grp-1", name="Finance")})
        groups = connector._get_groups(ep)
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].uid == "grp-1"
        assert groups[0].name == "Finance"

    def test_missing_group_returns_none(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"group": None})
        assert connector._get_groups(ep) is None

    def test_group_without_name_returns_none(self, connector):
        from sophos_module.asset_connector.model import SophosGroup

        ep = COMPUTER_ENDPOINT.model_copy(update={"group": SophosGroup(id="g1", name=None)})
        assert connector._get_groups(ep) is None

    def test_group_reflected_in_mapped_model(self, connector):
        """Group must appear in the OCSF model device.groups field."""
        from sophos_module.asset_connector.model import SophosGroup

        ep = COMPUTER_ENDPOINT.model_copy(update={"group": SophosGroup(id="grp-42", name="IT-Ops")})
        result = connector.map_device_fields(ep)
        assert result is not None
        assert result.device.groups is not None
        assert result.device.groups[0].name == "IT-Ops"


class TestIsTrusted:
    def test_good_health_and_tamper_enabled_is_trusted(self):
        ep = SophosEndpoint(
            id="x",
            hostname="h",
            health=SophosHealth(overall="good"),
            tamperProtectionEnabled=True,
            isolation=SophosIsolation(status="notIsolated"),
        )
        assert SophosDeviceAssetConnector._is_trusted(ep) is True

    def test_isolated_is_not_trusted(self):
        ep = SophosEndpoint(
            id="x",
            hostname="h",
            health=SophosHealth(overall="good"),
            tamperProtectionEnabled=True,
            isolation=SophosIsolation(status="isolated"),
        )
        assert SophosDeviceAssetConnector._is_trusted(ep) is False

    def test_bad_health_is_not_trusted(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="bad"))
        assert SophosDeviceAssetConnector._is_trusted(ep) is False

    def test_suspicious_health_is_not_trusted(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="suspicious"))
        assert SophosDeviceAssetConnector._is_trusted(ep) is False

    def test_unknown_state_returns_none(self):
        ep = SophosEndpoint(id="x", hostname="h", health=SophosHealth(overall="unknown"))
        assert SophosDeviceAssetConnector._is_trusted(ep) is None

    def test_good_health_but_tamper_disabled_returns_none(self):
        ep = SophosEndpoint(
            id="x",
            hostname="h",
            health=SophosHealth(overall="good"),
            tamperProtectionEnabled=False,
        )
        assert SophosDeviceAssetConnector._is_trusted(ep) is None


class TestIterEndpointsWithCheckpoint:
    def test_last_seen_cursor_passed_as_param(self, connector):
        """When a checkpoint exists, lastSeenAfter must be sent to the API."""
        with connector.context as cache:
            cache["last_seen_cursor"] = "2026-05-30T00:00:00.000Z"

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": [], "pages": {"size": 50, "maxSize": 500}}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp

        list(connector._iter_endpoints())

        called_params = connector.client.list_endpoints.call_args[0][0]
        assert called_params.get("lastSeenAfter") == "2026-05-30T00:00:00.000Z"

    def test_no_cursor_does_not_add_param(self, connector):
        """Without a checkpoint, lastSeenAfter must NOT be in the request params."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": [], "pages": {"size": 50, "maxSize": 500}}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp

        list(connector._iter_endpoints())

        called_params = connector.client.list_endpoints.call_args[0][0]
        assert "lastSeenAfter" not in called_params


class TestGetAssetsDeduplication:
    def test_deduplicates_same_inventory(self, connector):
        """Second run with identical inventory data must not re-send the device."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        assets_run1 = list(connector.get_assets())
        assert len(assets_run1) == 2

        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        assets_run2 = list(connector.get_assets())
        assert len(assets_run2) == 0

    def test_heartbeat_only_update_is_suppressed(self, connector):
        """A lastSeenAt-only change must NOT trigger a re-send."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        heartbeat = {**COMPUTER_ENDPOINT_DICT, "lastSeenAt": "2026-06-01T10:00:00.000Z"}
        _make_response(connector, [heartbeat])
        assets_run2 = list(connector.get_assets())
        assert len(assets_run2) == 0

    def test_real_inventory_change_is_resent(self, connector):
        """A change in a meaningful field (e.g. health) must trigger a re-send."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        updated = {**COMPUTER_ENDPOINT_DICT, "health": {"overall": "good"}}
        _make_response(connector, [updated])
        assets_run2 = list(connector.get_assets())
        assert len(assets_run2) == 1

    def test_new_device_sent_on_second_run(self, connector):
        """A brand-new device (not in cache) must be yielded on the second run."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        new_device = {
            **SERVER_ENDPOINT_DICT,
            "id": "aaaaaaaa-ffff-ffff-ffff-000000000099",
            "hostname": "new-server-99",
        }
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, new_device])
        assets_run2 = list(connector.get_assets())
        assert len(assets_run2) == 1
        assert assets_run2[0].device.hostname == "new-server-99"

    def test_cache_saved_even_on_exception(self, connector):
        """sent_ids must be persisted even when an exception is raised mid-collection."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 503")
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp

        with pytest.raises(Exception, match="HTTP 503"):
            list(connector.get_assets())

        with connector.context as cache:
            assert "sent_ids" in cache

    def test_ids_added_to_cache_after_run(self, connector):
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        list(connector.get_assets())

        with connector.context as cache:
            sent = cache.get("sent_ids", {})
        assert "aaaaaaaa-0000-0000-0000-000000000001" in sent
        assert "aaaaaaaa-0000-0000-0000-000000000002" in sent

    def test_cache_entry_has_fingerprint_and_cached_at(self, connector):
        """Each cache entry must contain both 'fingerprint' and 'cached_at' keys."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        with connector.context as cache:
            entry = cache.get("sent_ids", {}).get(COMPUTER_ENDPOINT_DICT["id"])
        assert entry is not None
        assert "fingerprint" in entry
        assert "cached_at" in entry

    def test_device_re_sent_after_ttl_expires(self, connector):
        """After cache TTL expires, the same device must be sent again on the next run."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        # Manually expire the cache entry by backdating its cached_at
        expired_ts = (datetime.now(tz=timezone.utc) - timedelta(days=connector.CACHE_MAX_AGE_DAYS + 1)).isoformat()
        with connector.context as cache:
            cache["sent_ids"][COMPUTER_ENDPOINT_DICT["id"]]["cached_at"] = expired_ts

        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        assets_run2 = list(connector.get_assets())
        assert len(assets_run2) == 1

    def test_multiple_inventory_changes_each_trigger_resend(self, connector):
        """Every distinct inventory change must produce a new send."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())  # run 1: initial send

        change1 = {**COMPUTER_ENDPOINT_DICT, "health": {"overall": "good"}}
        _make_response(connector, [change1])
        run2 = list(connector.get_assets())  # run 2: health changed
        assert len(run2) == 1

        change2 = {**change1, "ipv4Addresses": ["10.0.0.99"]}
        _make_response(connector, [change2])
        run3 = list(connector.get_assets())  # run 3: IP changed
        assert len(run3) == 1

        _make_response(connector, [change2])
        run4 = list(connector.get_assets())  # run 4: no change
        assert len(run4) == 0

    def test_deduplicated_count_logged(self, connector):
        """The completion log must report the number of deduplicated entries."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        list(connector.get_assets())  # seeds cache

        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        list(connector.get_assets())  # both deduped

        log_calls = [str(call) for call in connector.log.call_args_list]
        assert any("deduplicated=2" in call for call in log_calls)

    def test_mixed_new_and_cached_devices(self, connector):
        """In a batch with both cached and new devices, only new ones are yielded."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())  # cache computer

        new_device = {
            **SERVER_ENDPOINT_DICT,
            "id": "aaaaaaaa-ffff-ffff-ffff-000000000099",
            "hostname": "brand-new-host",
        }
        # computer (cached) + new_device (not cached) + server (cached)
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, new_device, SERVER_ENDPOINT_DICT])
        # Note: SERVER_ENDPOINT_DICT was never sent before so it will also be sent
        assets = list(connector.get_assets())
        hostnames = {a.device.hostname for a in assets}
        assert "brand-new-host" in hostnames
        assert "test-server-01" in hostnames
        assert "test-computer-01" not in hostnames  # was cached

    def test_cache_fingerprint_updated_after_change(self, connector):
        """After a change is detected and sent, the new fingerprint must be stored."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT])
        list(connector.get_assets())

        with connector.context as cache:
            original_fp = cache["sent_ids"][COMPUTER_ENDPOINT_DICT["id"]]["fingerprint"]

        updated = {**COMPUTER_ENDPOINT_DICT, "health": {"overall": "good"}}
        _make_response(connector, [updated])
        list(connector.get_assets())

        with connector.context as cache:
            new_fp = cache["sent_ids"][COMPUTER_ENDPOINT_DICT["id"]]["fingerprint"]

        assert new_fp != original_fp


class TestGetMappedFields:
    def test_returns_dict(self, connector):
        result = connector.get_mapped_fields()
        assert isinstance(result, dict)

    def test_is_non_empty(self, connector):
        assert len(connector.get_mapped_fields()) > 0

    def test_all_keys_and_values_are_strings(self, connector):
        mapping = connector.get_mapped_fields()
        for k, v in mapping.items():
            assert isinstance(k, str), f"Key {k!r} is not a string"
            assert isinstance(v, str), f"Value {v!r} is not a string"

    def test_contains_hostname_mapping(self, connector):
        assert "hostname" in connector.get_mapped_fields()

    def test_contains_os_mapping(self, connector):
        mapping = connector.get_mapped_fields()
        assert any("os" in k for k in mapping)

    def test_contains_ip_mapping(self, connector):
        mapping = connector.get_mapped_fields()
        assert any("ipv4" in k.lower() or "ipv6" in k.lower() for k in mapping)

    def test_contains_timestamp_mappings(self, connector):
        mapping = connector.get_mapped_fields()
        assert "lastSeenAt" in mapping
        assert "registeredAt" in mapping

    def test_deterministic_across_calls(self, connector):
        assert connector.get_mapped_fields() == connector.get_mapped_fields()

    def test_values_reference_device_namespace(self, connector):
        """All OCSF paths must point into the device object or enrichments."""
        for v in connector.get_mapped_fields().values():
            assert v.startswith("device.") or v.startswith(
                "enrichments."
            ), f"Expected OCSF path to start with 'device.' or 'enrichments.', got {v!r}"


class TestResetCheckpoint:
    def test_clears_last_seen_cursor_from_context(self, connector):
        with connector.context as cache:
            cache["last_seen_cursor"] = "2026-01-01T00:00:00.000Z"

        connector.reset_checkpoint()

        with connector.context as cache:
            assert cache.get("last_seen_cursor") is None

    def test_clears_sent_ids_from_context(self, connector):
        with connector.context as cache:
            cache["sent_ids"] = {"some-id": {"fingerprint": "fp", "cached_at": "2026-01-01T00:00:00Z"}}

        connector.reset_checkpoint()

        with connector.context as cache:
            assert cache.get("sent_ids") is None

    def test_resets_latest_time_in_memory(self, connector):
        connector._latest_time = "2026-05-01T00:00:00.000Z"
        connector.reset_checkpoint()
        assert connector._latest_time is None

    def test_resets_sent_ids_in_memory(self, connector):
        connector._sent_ids = {"id-1": {"fingerprint": "fp", "cached_at": "2026-01-01T00:00:00Z"}}
        connector.reset_checkpoint()
        assert connector._sent_ids == {}

    def test_logs_info_message(self, connector):
        connector.reset_checkpoint()
        log_calls = [str(call) for call in connector.log.call_args_list]
        assert any("reset" in call.lower() for call in log_calls)

    def test_noop_on_empty_context(self, connector):
        """reset_checkpoint must not raise when the context is already empty."""
        connector.reset_checkpoint()  # must not raise

    def test_full_refetch_after_reset(self, connector):
        """After reset, the next get_assets() run must re-yield all devices."""
        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        list(connector.get_assets())  # seeds cache

        connector.reset_checkpoint()

        _make_response(connector, [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        assets = list(connector.get_assets())
        assert len(assets) == 2

    def test_checkpoint_cleared_means_no_cursor_on_next_iter(self, connector):
        """After reset, _iter_endpoints must not pass lastSeenAfter."""
        with connector.context as cache:
            cache["last_seen_cursor"] = "2026-05-30T00:00:00.000Z"

        connector.reset_checkpoint()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": [], "pages": {"size": 50, "maxSize": 500}}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp

        list(connector._iter_endpoints())

        called_params = connector.client.list_endpoints.call_args[0][0]
        assert "lastSeenAfter" not in called_params
