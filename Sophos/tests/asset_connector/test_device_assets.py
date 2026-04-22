"""
Unit tests for SophosDeviceAssetConnector (asset_connector/device_assets.py).
"""
from unittest.mock import MagicMock

import pytest
import requests_mock as req_mock

from sophos_module.base import SophosModule
from sophos_module.asset_connector.device_assets import SophosDeviceAssetConnector
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)

# ---------------------------------------------------------------------------
# Sample API response payloads
# ---------------------------------------------------------------------------

COMPUTER_ENDPOINT = {
    "id": "51a8f1a0-db9d-4980-a201-7e1d97ca5877",
    "type": "computer",
    "tenant": {"id": "4feff6df-7454-4036-923d-7b2444462416"},
    "hostname": "mymjnbegguqa-vm",
    "health": {"overall": "bad", "threats": {"status": "good"}, "services": {"status": "bad"}},
    "os": {"isServer": False, "platform": "windows", "name": "Windows 10 Pro N", "majorVersion": 10, "minorVersion": 0, "build": 19044},
    "ipv4Addresses": ["10.0.4.4"],
    "ipv6Addresses": [],
    "macAddresses": ["00:22:48:37:FE:2F", "00:FF:2F:8A:93:75"],
    "tamperProtectionEnabled": True,
    "associatedPerson": {"name": "mymjnbegguqa-vm\\adminuser", "viaLogin": "mymjnbegguqa-vm\\adminuser", "id": "c8c3f320"},
    "lastSeenAt": "2024-01-07T06:26:08.668Z",
    "registeredAt": "2023-06-26T10:28:08.836Z",
    "cloud": {"provider": "azure", "instanceId": "7bb240a3"},
    "isolation": {"status": "notIsolated", "adminIsolated": False, "selfIsolated": False},
    "online": False,
    "tags": [],
}

SERVER_ENDPOINT = {
    "id": "a92622ec-6a11-4b1b-b179-780d520bf8e6",
    "type": "server",
    "tenant": {"id": "4feff6df-7454-4036-923d-7b2444462416"},
    "hostname": "ubuntu-xenial",
    "health": {"overall": "good", "threats": {"status": "good"}, "services": {"status": "good"}},
    "os": {"isServer": True, "platform": "linux", "name": "Ubuntu 16.04.7 LTS"},
    "ipv4Addresses": ["10.0.2.15"],
    "ipv6Addresses": ["fe80::be:82ff:fe6b:cc1d"],
    "macAddresses": ["02:be:82:6b:cc:1d"],
    "tamperProtectionEnabled": False,
    "associatedPerson": {},
    "lastSeenAt": "2025-01-06T11:24:27.741Z",
    "registeredAt": "2024-09-30T07:13:25.289Z",
    "online": False,
    "tags": [],
}

MINIMAL_ENDPOINT = {
    "id": "aaa-bbb-ccc",
    "type": "computer",
    "tenant": {"id": "tenant-123"},
    "hostname": "minimal-host",
    "health": {"overall": "good"},
    "os": {"platform": "macos", "name": "macOS 14"},
    "ipv4Addresses": [],
    "macAddresses": [],
    "tamperProtectionEnabled": None,
    "associatedPerson": {},
    "lastSeenAt": None,
    "registeredAt": None,
    "online": True,
    "tags": [],
}

API_RESPONSE_PAGE1 = {
    "items": [COMPUTER_ENDPOINT, SERVER_ENDPOINT],
    "pages": {"size": 50, "maxSize": 500, "nextKey": "page2key"},
}

API_RESPONSE_PAGE2 = {
    "items": [MINIMAL_ENDPOINT],
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
    "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
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
        assert os_obj.name == "Windows 10 Pro N"

    def test_linux(self, connector):
        os_obj = connector._get_os(SERVER_ENDPOINT)
        assert os_obj.type_id == OSTypeId.LINUX
        assert os_obj.type == OSTypeStr.LINUX

    def test_macos(self, connector):
        os_obj = connector._get_os({"os": {"platform": "macos", "name": "macOS 14"}})
        assert os_obj.type_id == OSTypeId.MACOS

    def test_android(self, connector):
        os_obj = connector._get_os({"os": {"platform": "android", "name": "Android 13"}})
        assert os_obj.type_id == OSTypeId.ANDROID

    def test_unknown_platform(self, connector):
        os_obj = connector._get_os({"os": {"platform": "exotic", "name": "Exotic OS"}})
        assert os_obj.type_id == OSTypeId.UNKNOWN

    def test_missing_os_key(self, connector):
        os_obj = connector._get_os({})
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
        type_id, type_str = SophosDeviceAssetConnector._get_device_type({"type": "tablet"})
        assert type_id == DeviceTypeId.UNKNOWN

    def test_missing_key(self):
        type_id, _ = SophosDeviceAssetConnector._get_device_type({})
        assert type_id == DeviceTypeId.UNKNOWN


class TestGetNetworkInterfaces:
    def test_single_ipv4_with_mac(self):
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(COMPUTER_ENDPOINT)
        assert interfaces is not None
        assert len(interfaces) == 1
        iface = interfaces[0]
        assert iface.ip == "10.0.4.4"
        assert iface.mac == "00:22:48:37:FE:2F"
        assert iface.hostname == "mymjnbegguqa-vm"
        assert iface.name == "eth0"

    def test_ipv4_and_ipv6(self):
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(SERVER_ENDPOINT)
        assert interfaces is not None
        assert len(interfaces) == 2
        assert interfaces[0].ip == "10.0.2.15"
        assert interfaces[1].ip == "fe80::be:82ff:fe6b:cc1d"

    def test_no_addresses_returns_none(self):
        result = SophosDeviceAssetConnector._get_network_interfaces(
            {"ipv4Addresses": [], "ipv6Addresses": [], "macAddresses": []}
        )
        assert result is None

    def test_mac_normalization(self):
        endpoint = {
            "hostname": "h",
            "ipv4Addresses": ["1.2.3.4"],
            "ipv6Addresses": [],
            "macAddresses": ["aa-bb-cc-dd-ee-ff"],
        }
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(endpoint)
        assert interfaces[0].mac == "AA:BB:CC:DD:EE:FF"

    def test_hostname_only_on_first_interface(self):
        endpoint = {
            "hostname": "myhost",
            "ipv4Addresses": ["1.1.1.1", "2.2.2.2"],
            "ipv6Addresses": [],
            "macAddresses": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"],
        }
        interfaces = SophosDeviceAssetConnector._get_network_interfaces(endpoint)
        assert interfaces[0].hostname == "myhost"
        assert interfaces[1].hostname is None


class TestNormalizeMac:
    def test_dashes_to_colons(self):
        assert SophosDeviceAssetConnector._normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"

    def test_already_correct(self):
        assert SophosDeviceAssetConnector._normalize_mac("00:22:48:37:FE:2F") == "00:22:48:37:FE:2F"

    def test_none_input(self):
        assert SophosDeviceAssetConnector._normalize_mac(None) is None

    def test_empty_string(self):
        assert SophosDeviceAssetConnector._normalize_mac("") is None


class TestIsCompliant:
    def test_good(self):
        assert SophosDeviceAssetConnector._is_compliant({"health": {"overall": "good"}}) is True

    def test_bad(self):
        assert SophosDeviceAssetConnector._is_compliant({"health": {"overall": "bad"}}) is False

    def test_suspicious(self):
        assert SophosDeviceAssetConnector._is_compliant({"health": {"overall": "suspicious"}}) is False

    def test_unknown_value(self):
        assert SophosDeviceAssetConnector._is_compliant({"health": {"overall": "unknown"}}) is None

    def test_missing_health(self):
        assert SophosDeviceAssetConnector._is_compliant({}) is None


class TestGetFirewallStatus:
    def test_enabled(self):
        assert SophosDeviceAssetConnector._get_firewall_status({"tamperProtectionEnabled": True}) == "Enabled"

    def test_disabled(self):
        assert SophosDeviceAssetConnector._get_firewall_status({"tamperProtectionEnabled": False}) == "Disabled"

    def test_none_value(self):
        assert SophosDeviceAssetConnector._get_firewall_status({"tamperProtectionEnabled": None}) is None

    def test_missing_key(self):
        assert SophosDeviceAssetConnector._get_firewall_status({}) is None


class TestGetOrganization:
    def test_tenant_present(self):
        org = SophosDeviceAssetConnector._get_organization(COMPUTER_ENDPOINT)
        assert org is not None
        assert org.uid == "4feff6df-7454-4036-923d-7b2444462416"

    def test_tenant_missing(self):
        assert SophosDeviceAssetConnector._get_organization({}) is None

    def test_tenant_empty_id(self):
        assert SophosDeviceAssetConnector._get_organization({"tenant": {"id": ""}}) is None


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
        assert result.device.uid == "51a8f1a0-db9d-4980-a201-7e1d97ca5877"
        assert result.device.hostname == "mymjnbegguqa-vm"
        assert result.device.type_id == DeviceTypeId.DESKTOP
        assert result.device.os.type_id == OSTypeId.WINDOWS
        assert result.device.ip == "10.0.4.4"
        assert result.device.is_compliant is False
        assert result.device.is_managed is True
        assert result.device.region == "azure"
        assert result.device.desc == "mymjnbegguqa-vm\\adminuser"
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
        endpoint = {**COMPUTER_ENDPOINT, "id": None}
        assert connector.map_device_fields(endpoint) is None
        connector.log.assert_called()

    def test_missing_hostname_returns_none(self, connector):
        endpoint = {**COMPUTER_ENDPOINT, "hostname": None}
        assert connector.map_device_fields(endpoint) is None

    def test_no_cloud_field(self, connector):
        endpoint = {k: v for k, v in COMPUTER_ENDPOINT.items() if k != "cloud"}
        result = connector.map_device_fields(endpoint)
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
            "items": [COMPUTER_ENDPOINT, SERVER_ENDPOINT],
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


class TestGetAssets:
    def test_yields_valid_models(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "items": [COMPUTER_ENDPOINT, SERVER_ENDPOINT],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        assets = list(connector.get_assets())
        assert len(assets) == 2

    def test_skips_invalid_endpoints(self, connector):
        no_id = {**COMPUTER_ENDPOINT, "id": None}
        no_hostname = {**SERVER_ENDPOINT, "hostname": ""}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "items": [no_id, no_hostname, MINIMAL_ENDPOINT],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        assets = list(connector.get_assets())
        assert len(assets) == 1  # only MINIMAL_ENDPOINT

    def test_raises_on_http_error(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_response

        with pytest.raises(Exception, match="HTTP 500"):
            list(connector.get_assets())

    def test_update_checkpoint_is_noop(self, connector):
        connector.update_checkpoint()  # must not raise


class TestFullHttpRoundTrip:
    def test_collect_endpoints_via_http(self, connector):
        data_region = "https://api-eu01.central.sophos.com"

        with req_mock.Mocker() as m:
            m.post(AUTH_URL, json=AUTH_TOKEN_RESPONSE, status_code=200)
            m.get("https://api.central.sophos.com/whoami/v1", json=WHOAMI_RESPONSE, status_code=200)
            m.get(
                f"{data_region}/endpoint/v1/endpoints",
                json={"items": [COMPUTER_ENDPOINT, SERVER_ENDPOINT], "pages": {"size": 50, "maxSize": 500}},
                status_code=200,
            )

            # Remove cached client so it's rebuilt with real HTTP session
            if "client" in connector.__dict__:
                del connector.__dict__["client"]

            assets = list(connector.get_assets())

        assert len(assets) == 2
        hostnames = {a.device.hostname for a in assets}
        assert "mymjnbegguqa-vm" in hostnames
        assert "ubuntu-xenial" in hostnames

