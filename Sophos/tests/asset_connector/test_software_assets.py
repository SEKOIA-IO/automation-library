"""
Unit tests for SophosSoftwareAssetConnector (asset_connector/software_assets.py).

Data source: endpoint.modules from GET /endpoint/v1/endpoints.
Each module represents a Sophos software component installed on the endpoint.
"""

from unittest.mock import MagicMock

import pytest
import requests_mock as req_mock

from sophos_module.base import SophosModule
from sophos_module.asset_connector.software_assets import SophosSoftwareAssetConnector
from sophos_module.asset_connector.model import (
    SophosEndpoint,
    SophosOS,
    SophosTenant,
    SophosModule_,
)
from sekoia_automation.asset_connector.models.ocsf.device import DeviceTypeId, OSTypeId

# ---------------------------------------------------------------------------
# Sample data — realistic payloads from the real API
# ---------------------------------------------------------------------------

MODULE_CORE = SophosModule_(name="coreAgent", version="2024.2.4.1.0")
MODULE_INTERCEPT = SophosModule_(name="interceptX", version="2024.1.2.1.0")
MODULE_ENCRYPTION = SophosModule_(name="deviceEncryption", version="2024.2.1.6.0")
MODULE_NO_NAME = SophosModule_(name=None, version="1.0")
MODULE_NO_VERSION = SophosModule_(name="coreAgent", version=None)

COMPUTER_ENDPOINT = SophosEndpoint(
    id="aaaaaaaa-0000-0000-0000-000000000001",
    type="computer",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    hostname="test-computer-01",
    os=SophosOS(platform="windows", name="Windows 10 Pro"),
    ipv4Addresses=["192.0.2.1"],
    ipv6Addresses=[],
    macAddresses=["AA:BB:CC:DD:EE:01"],
    lastSeenAt="2024-01-07T06:26:08.668Z",
    modules=[MODULE_CORE, MODULE_INTERCEPT, MODULE_ENCRYPTION],
)

SERVER_ENDPOINT = SophosEndpoint(
    id="aaaaaaaa-0000-0000-0000-000000000002",
    type="server",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    hostname="test-server-01",
    os=SophosOS(platform="linux", name="Ubuntu 22.04"),
    ipv4Addresses=["192.0.2.2"],
    lastSeenAt="2025-01-06T11:24:27.741Z",
    modules=[SophosModule_(name="coreAgent", version="2024.2.1.2")],
)

# Dict versions for HTTP-level mock tests (matches real API format)
COMPUTER_ENDPOINT_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "type": "computer",
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "hostname": "test-computer-01",
    "os": {"platform": "windows", "name": "Windows 10 Pro"},
    "ipv4Addresses": ["192.0.2.1"],
    "ipv6Addresses": [],
    "macAddresses": ["AA:BB:CC:DD:EE:01"],
    "lastSeenAt": "2024-01-07T06:26:08.668Z",
    "modules": [
        {"name": "coreAgent", "version": "2024.2.4.1.0"},
        {"name": "interceptX", "version": "2024.1.2.1.0"},
        {"name": "deviceEncryption", "version": "2024.2.1.6.0"},
    ],
    "tags": [],
}

SERVER_ENDPOINT_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000002",
    "type": "server",
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "hostname": "test-server-01",
    "os": {"platform": "linux", "name": "Ubuntu 22.04"},
    "ipv4Addresses": ["192.0.2.2"],
    "ipv6Addresses": [],
    "macAddresses": [],
    "lastSeenAt": "2025-01-06T11:24:27.741Z",
    "modules": [
        {"name": "coreAgent", "version": "2024.2.1.2"},
    ],
    "tags": [],
}

ENDPOINT_NO_MODULES = {
    "id": "aaaaaaaa-0000-0000-0000-000000000003",
    "type": "computer",
    "hostname": "no-modules-host",
    "os": {"platform": "windows"},
    "ipv4Addresses": ["10.0.0.1"],
    "modules": [],
    "tags": [],
}

AUTH_TOKEN_RESPONSE = {
    "access_token": "test_access_token",
    "token_type": "bearer",
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
    c = SophosSoftwareAssetConnector(module=module, data_path=symphony_storage)
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


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------

class TestGetOs:
    def test_windows(self, connector):
        os_obj = connector._get_os(COMPUTER_ENDPOINT)
        assert os_obj.type_id == OSTypeId.WINDOWS
        assert os_obj.name == "Windows 10 Pro"

    def test_linux(self, connector):
        assert connector._get_os(SERVER_ENDPOINT).type_id == OSTypeId.LINUX

    def test_unknown_platform(self, connector):
        ep = SophosEndpoint(id="x", hostname="h", os=SophosOS(platform="exotic"))
        assert connector._get_os(ep).type_id == OSTypeId.UNKNOWN

    def test_no_os(self, connector):
        ep = SophosEndpoint(id="x", hostname="h")
        assert connector._get_os(ep).type_id == OSTypeId.UNKNOWN


class TestGetDeviceType:
    def test_computer(self):
        type_id, _ = SophosSoftwareAssetConnector._get_device_type(COMPUTER_ENDPOINT)
        assert type_id == DeviceTypeId.DESKTOP

    def test_server(self):
        type_id, _ = SophosSoftwareAssetConnector._get_device_type(SERVER_ENDPOINT)
        assert type_id == DeviceTypeId.SERVER

    def test_unknown(self):
        ep = SophosEndpoint(id="x", hostname="h", type="tablet")
        type_id, _ = SophosSoftwareAssetConnector._get_device_type(ep)
        assert type_id == DeviceTypeId.UNKNOWN


class TestParseTs:
    def test_valid_iso(self):
        ts = SophosSoftwareAssetConnector._parse_ts("2024-01-07T06:26:08.668Z")
        assert isinstance(ts, float) and ts > 0

    def test_none(self):
        assert SophosSoftwareAssetConnector._parse_ts(None) is None

    def test_empty_string(self):
        assert SophosSoftwareAssetConnector._parse_ts("") is None

    def test_invalid(self):
        assert SophosSoftwareAssetConnector._parse_ts("not-a-date") is None


# ---------------------------------------------------------------------------
# map_software_fields
# ---------------------------------------------------------------------------

class TestMapSoftwareFields:
    def test_basic_mapping(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_CORE)
        assert result is not None
        assert result.device.uid == "aaaaaaaa-0000-0000-0000-000000000001"
        assert result.device.hostname == "test-computer-01"
        assert result.software.name == "coreAgent"
        assert result.software.version == "2024.2.4.1.0"
        assert result.software.vendor_name == "Sophos"
        assert result.class_uid == 5002
        assert result.type_uid == 500202
        assert result.activity_id == 2
        assert result.metadata.product.name == "Sophos EDR"

    def test_sbom_created_when_version_present(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_CORE)
        assert result is not None
        assert result.sbom is not None
        assert result.sbom.package.name == "coreAgent"
        assert result.sbom.package.version == "2024.2.4.1.0"

    def test_sbom_none_when_no_version(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_NO_VERSION)
        assert result is not None
        assert result.sbom is None

    def test_missing_endpoint_id_returns_none(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"id": None})
        assert connector.map_software_fields(ep, MODULE_CORE) is None
        connector.log.assert_called()

    def test_missing_endpoint_hostname_returns_none(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"hostname": None})
        assert connector.map_software_fields(ep, MODULE_CORE) is None

    def test_missing_module_name_returns_none(self, connector):
        assert connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_NO_NAME) is None

    def test_event_time_from_last_seen_at(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_CORE)
        assert result is not None
        expected_ts = SophosSoftwareAssetConnector._parse_ts("2024-01-07T06:26:08.668Z")
        assert result.time == expected_ts

    def test_event_time_fallback_when_no_last_seen(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"lastSeenAt": None})
        result = connector.map_software_fields(ep, MODULE_CORE)
        assert result is not None
        assert result.time > 0

    def test_device_ip_from_ipv4(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_CORE)
        assert result is not None
        assert result.device.ip == "192.0.2.1"

    def test_device_ip_fallback_ipv6(self, connector):
        ep = COMPUTER_ENDPOINT.model_copy(update={"ipv4Addresses": [], "ipv6Addresses": ["fe80::1"]})
        result = connector.map_software_fields(ep, MODULE_CORE)
        assert result is not None
        assert result.device.ip == "fe80::1"

    def test_ocsf_constants(self, connector):
        result = connector.map_software_fields(COMPUTER_ENDPOINT, MODULE_CORE)
        assert result is not None
        assert result.category_name == "Discovery"
        assert result.category_uid == 5
        assert result.class_name == "Software Inventory Info"
        assert result.severity == "Informational"
        assert result.severity_id == 1


# ---------------------------------------------------------------------------
# _iter_endpoints
# ---------------------------------------------------------------------------

class TestIterEndpoints:
    def test_single_page(self, connector):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT],
            "pages": {"size": 50, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp
        assert len(list(connector._iter_endpoints())) == 2

    def test_pagination(self, connector):
        mock_resp_1 = MagicMock()
        mock_resp_1.raise_for_status = MagicMock()
        mock_resp_1.json.return_value = {
            "items": [COMPUTER_ENDPOINT_DICT],
            "pages": {"size": 1, "maxSize": 500, "nextKey": "page2key"},
        }
        mock_resp_2 = MagicMock()
        mock_resp_2.raise_for_status = MagicMock()
        mock_resp_2.json.return_value = {
            "items": [SERVER_ENDPOINT_DICT],
            "pages": {"size": 1, "maxSize": 500},
        }
        connector.client = MagicMock()
        connector.client.list_endpoints.side_effect = [mock_resp_1, mock_resp_2]
        items = list(connector._iter_endpoints())
        assert len(items) == 2
        assert connector.client.list_endpoints.call_count == 2

    def test_stops_when_not_running(self, connector):
        type(connector).running = property(lambda self: False)
        connector.client = MagicMock()
        assert list(connector._iter_endpoints()) == []
        connector.client.list_endpoints.assert_not_called()


# ---------------------------------------------------------------------------
# get_assets
# ---------------------------------------------------------------------------

class TestGetAssets:
    def _mock_resp(self, data):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = data
        return m

    def _ep_response(self, items, next_key=None):
        pages = {"size": len(items), "maxSize": 500}
        if next_key:
            pages["nextKey"] = next_key
        return {"items": items, "pages": pages}

    def test_yields_one_model_per_module(self, connector):
        # COMPUTER_ENDPOINT_DICT has 3 modules → 3 assets
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(
            self._ep_response([COMPUTER_ENDPOINT_DICT])
        )
        assets = list(connector.get_assets())
        assert len(assets) == 3
        names = {a.software.name for a in assets}
        assert names == {"coreAgent", "interceptX", "deviceEncryption"}

    def test_vendor_name_is_sophos(self, connector):
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(
            self._ep_response([COMPUTER_ENDPOINT_DICT])
        )
        for asset in connector.get_assets():
            assert asset.software.vendor_name == "Sophos"

    def test_skips_endpoint_without_id(self, connector):
        no_id = {**COMPUTER_ENDPOINT_DICT, "id": None}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(self._ep_response([no_id]))
        assert list(connector.get_assets()) == []

    def test_skips_module_without_name(self, connector):
        ep = {**COMPUTER_ENDPOINT_DICT, "modules": [{"name": None, "version": "1.0"}, {"name": "coreAgent", "version": "1.0"}]}
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(self._ep_response([ep]))
        assets = list(connector.get_assets())
        assert len(assets) == 1

    def test_endpoint_with_no_modules_yields_nothing(self, connector):
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(
            self._ep_response([ENDPOINT_NO_MODULES])
        )
        assert list(connector.get_assets()) == []

    def test_aggregates_multiple_endpoints(self, connector):
        # computer: 3 modules, server: 1 module → 4 assets total
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(
            self._ep_response([COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT])
        )
        assert len(list(connector.get_assets())) == 4

    def test_raises_on_http_error(self, connector):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = mock_resp
        with pytest.raises(Exception, match="HTTP 500"):
            list(connector.get_assets())

    def test_device_fields_on_asset(self, connector):
        connector.client = MagicMock()
        connector.client.list_endpoints.return_value = self._mock_resp(
            self._ep_response([COMPUTER_ENDPOINT_DICT])
        )
        assets = list(connector.get_assets())
        for asset in assets:
            assert asset.device.uid == "aaaaaaaa-0000-0000-0000-000000000001"
            assert asset.device.hostname == "test-computer-01"
            assert asset.device.ip == "192.0.2.1"


# ---------------------------------------------------------------------------
# Full HTTP round-trip
# ---------------------------------------------------------------------------

class TestFullHttpRoundTrip:
    def test_collect_modules_via_http(self, connector):
        data_region = "https://api-eu01.central.sophos.com"

        with req_mock.Mocker() as m:
            m.post(AUTH_URL, json=AUTH_TOKEN_RESPONSE, status_code=200)
            m.get("https://api.central.sophos.com/whoami/v1", json=WHOAMI_RESPONSE, status_code=200)
            m.get(
                f"{data_region}/endpoint/v1/endpoints",
                json={
                    "items": [COMPUTER_ENDPOINT_DICT, SERVER_ENDPOINT_DICT],
                    "pages": {"size": 50, "maxSize": 500},
                },
                status_code=200,
            )

            if "client" in connector.__dict__:
                del connector.__dict__["client"]

            assets = list(connector.get_assets())

        # computer has 3 modules + server has 1 → 4 total
        assert len(assets) == 4
        hostnames = {a.device.hostname for a in assets}
        assert "test-computer-01" in hostnames
        assert "test-server-01" in hostnames
        names = {a.software.name for a in assets}
        assert "coreAgent" in names
        assert "interceptX" in names
        assert "deviceEncryption" in names
        for asset in assets:
            assert asset.software.vendor_name == "Sophos"
