import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest
import requests
import requests_mock
import yaml
from pydantic import ValidationError
from sekoia_automation.asset_connector.models.ocsf.device import DeviceTypeId, OSTypeId

from withsecure import WithSecureModule
from withsecure.asset_connector.device_assets import WithSecureDeviceAssetConnector
from withsecure.asset_connector.models import WithSecureDevice
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.constants import API_LIST_DEVICES_URL

SERVER_DEVICE = {
    "id": "e297cbf5-ba53-4e66-909c-000000000000",
    "name": "SRV-WEB-01",
    "type": "computer",
    "state": "active",
    "company": {"name": "Example company", "id": "00000000-0000-0000-0000-000000000000"},
    "assetGroups": [{"id": "11111111-1111-1111-1111-111111111111", "name": "Servers"}],
    "subscription": {
        "productVariant": "serverprotection_premium_rdr",
        "name": "EDR and EPP for Servers Premium",
        "key": "0000-0000-0000-0000-0000",
    },
    "os": {"name": "Windows Server 2022", "version": "21H2", "endOfLife": False},
    "lastUser": "SRV-WEB-01\\Administrator",
    "userPrincipalName": "",
    "dnsAddress": "SRV-WEB-01",
    "firewallState": "disabledByGpoOk",
    "protectionStatusOverview": "allOk",
    "macAddresses": "0E-E3-1C-E3-00-00",
    "ipAddresses": "172.31.40.211/20",
    "publicIpAddress": "203.0.113.73",
    "computerModel": "t3.large",
    "serialNumber": "ec298270-651b-f728-d6be-000000000000",
    "discEncryptionEnabled": False,
    "statusUpdateTimestamp": "2023-05-20T13:15:16.550Z",
    "registrationTimestamp": "2023-05-17T06:42:03.062Z",
    "lastRestartTime": "2023-05-19T08:00:00Z",
    "vmRiskScore": 42,
    "online": True,
}

DESKTOP_DEVICE = {
    "id": "aaaaaaaa-0000-0000-0000-000000000002",
    "name": "LAPTOP-01",
    "type": "computer",
    "subscription": {"productVariant": "computerprotection_premium_edr"},
    "os": {"name": "Windows 11"},
    "dnsAddress": "laptop-01.corp.example.com",
    "firewallState": "enabled",
    "protectionStatusOverview": "critical",
    "ipAddresses": "192.0.2.10/24,198.51.100.4/24",
    "ipv6Addresses": "fe80::1",
    "macAddresses": "AA-BB-CC-DD-EE-01,AA-BB-CC-DD-EE-02,AA-BB-CC-DD-EE-03,AA-BB-CC-DD-EE-04",
    "lastUser": "CORP\\jdoe",
    "userPrincipalName": "jdoe@corp.example.com",
    "encryptedDrives": [
        {"drive": "C:", "protectionStatus": True},
        {"drive": "D:", "protectionStatus": False},
        {"drive": "E:", "protectionStatus": None},
    ],
    "discEncryptionEnabled": True,
    "statusUpdateTimestamp": "2023-05-21T10:00:00Z",
}

MOBILE_DEVICE = {
    "id": "aaaaaaaa-0000-0000-0000-000000000003",
    "name": "Pixel 8",
    "type": "mobile",
    "os": {"name": "Android", "version": "14", "securityPatch": "2024-01-01"},
    "email": "jdoe@corp.example.com",
    "protectionStatusOverview": "inactive",
    "statusUpdateTimestamp": "2023-05-19T10:00:00Z",
}

RELAY_DEVICE = {
    "id": "aaaaaaaa-0000-0000-0000-000000000004",
    "name": "relay-01",
    "type": "connector",
    "online": True,
}


@pytest.fixture
def connector(data_storage, mocker):
    mocker.patch.object(WithSecureDeviceAssetConnector, "running", new_callable=PropertyMock, return_value=True)
    module = WithSecureModule()
    connector = WithSecureDeviceAssetConnector(module=module, data_path=data_storage)
    connector.module.configuration = {"client_id": "fusion_0000", "secret": "0000"}
    connector.configuration = {
        "sekoia_base_url": "https://api.sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 21600,
        "batch_size": 100,
    }
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    return connector


@pytest.fixture
def api():
    with requests_mock.Mocker() as mock:
        mock.post(API_AUTHENTICATION_URL, json={"access_token": "token", "expires_in": 1799})
        yield mock


def map_device(connector, payload):
    return connector.map_fields(WithSecureDevice.model_validate(payload))


def test_map_server(connector):
    asset = map_device(connector, SERVER_DEVICE)
    device = asset.device

    assert asset.class_uid == 5001
    assert asset.type_uid == 500102
    assert asset.metadata.product.name == "WithSecure Elements"
    assert asset.time == device.last_seen_time
    assert device.uid == SERVER_DEVICE["id"]
    assert device.hostname == device.name == "SRV-WEB-01"
    assert device.type_id == DeviceTypeId.SERVER
    assert device.os.name == "Windows Server 2022 21H2"
    assert device.os.type_id == OSTypeId.WINDOWS
    assert device.ip == "172.31.40.211"
    assert device.subnet == "172.31.32.0/20"
    assert [(i.ip, i.mac, i.hostname) for i in device.network_interfaces] == [
        ("172.31.40.211", "0E:E3:1C:E3:00:00", "SRV-WEB-01"),
    ]
    assert device.model == "t3.large"
    assert device.vendor_name is None
    assert device.uid_alt == SERVER_DEVICE["serialNumber"]
    assert device.created_time == device.first_seen_time == 1684305723.062
    assert device.last_seen_time == 1684588516.55
    assert device.boot_time == 1684483200.0
    assert (device.org.uid, device.org.name) == (SERVER_DEVICE["company"]["id"], "Example company")
    assert [(g.uid, g.name) for g in device.groups] == [("11111111-1111-1111-1111-111111111111", "Servers")]
    assert device.is_managed is True
    assert device.is_compliant is True
    assert device.risk_score == 42

    data = asset.enrichments[0].data
    assert (asset.enrichments[0].name, asset.enrichments[0].value) == ("compliance", "hygiene")
    assert data.Firewall_status is None
    assert data.Storage_encryption.partitions == {"system": "Disabled"}
    assert data.Users == ["SRV-WEB-01\\Administrator"]
    assert data.Full_qualified_domain_name is None

    assert json.dumps(asset.model_dump(exclude_none=True))


def test_map_desktop(connector):
    device_asset = map_device(connector, DESKTOP_DEVICE)
    device = device_asset.device

    assert device.type_id == DeviceTypeId.DESKTOP
    assert device.os.name == "Windows 11"
    assert device.ip == "192.0.2.10"
    assert device.subnet == "192.0.2.0/24"
    assert device.is_compliant is False
    # several IPs and MACs are not paired; the link-local fe80::1 is dropped
    assert [(i.ip, i.mac, i.hostname) for i in device.network_interfaces] == [
        ("192.0.2.10", None, "LAPTOP-01"),
        ("198.51.100.4", None, None),
        (None, "AA:BB:CC:DD:EE:01", None),
        (None, "AA:BB:CC:DD:EE:02", None),
        (None, "AA:BB:CC:DD:EE:03", None),
        (None, "AA:BB:CC:DD:EE:04", None),
    ]

    data = device_asset.enrichments[0].data
    assert data.Firewall_status == "Enabled"
    assert data.Storage_encryption.partitions == {"C:": "Enabled", "D:": "Disabled"}
    assert data.Users == ["CORP\\jdoe", "jdoe@corp.example.com"]
    assert data.Full_qualified_domain_name == "laptop-01.corp.example.com"


def test_map_mobile(connector):
    asset = map_device(connector, MOBILE_DEVICE)

    assert asset.device.type_id == DeviceTypeId.MOBILE
    assert asset.device.os.type_id == OSTypeId.ANDROID
    assert asset.device.network_interfaces is None
    assert asset.device.is_compliant is None
    assert asset.enrichments[0].data.Users == ["jdoe@corp.example.com"]


def test_map_relay(connector):
    asset = map_device(connector, RELAY_DEVICE)

    assert asset.device.type_id == DeviceTypeId.SERVER
    assert asset.device.os is None
    assert asset.enrichments is None


def test_get_storage_encryption_skips_unknown_status():
    device = WithSecureDevice.model_validate(
        {"id": "x", "encryptedDrives": [{"drive": "C:"}], "discEncryptionEnabled": True}
    )
    assert WithSecureDeviceAssetConnector._get_storage_encryption(device).partitions == {"system": "Enabled"}


def test_map_tolerates_nulls_and_float_risk_score(connector):
    asset = map_device(
        connector,
        {
            "id": "x",
            "name": None,
            "assetGroups": None,
            "encryptedDrives": None,
            "company": None,
            "os": {"name": None},
            "vmRiskScore": 41.6,
        },
    )

    assert asset.device.hostname == "x"
    assert asset.device.groups is None
    assert asset.device.risk_score == 42


def test_map_minimal_device(connector):
    asset = map_device(connector, {"id": "only-id", "ipAddresses": "not-an-ip"})

    assert asset.device.hostname == "only-id"
    assert asset.device.type_id == DeviceTypeId.UNKNOWN
    assert asset.device.ip is None
    assert asset.device.network_interfaces is None
    assert asset.device.org is None
    assert asset.device.groups is None
    assert asset.enrichments is None
    assert asset.time > 0


@pytest.mark.parametrize(
    "os_name,expected",
    [
        ("macOS", OSTypeId.MACOS),
        ("iOS", OSTypeId.IOS),
        ("iPadOS", OSTypeId.IPADOS),
        ("Ubuntu 22.04", OSTypeId.LINUX),
        ("Red Hat Enterprise Linux", OSTypeId.LINUX),
        ("FreeBSD", OSTypeId.UNKNOWN),
    ],
)
def test_map_os_type(connector, os_name, expected):
    asset = map_device(connector, {"id": "x", "type": "computer", "os": {"name": os_name}})
    assert asset.device.os.type_id == expected


@pytest.mark.parametrize(
    "state,expected",
    [("enabled", "Enabled"), ("disabled", "Disabled"), ("disabledByGpo", "Disabled"), ("disabledOk", None)],
)
def test_map_firewall(connector, state, expected):
    asset = map_device(connector, {"id": "x", "firewallState": state, "lastUser": "user"})
    assert asset.enrichments[0].data.Firewall_status == expected


def test_get_assets_paginates_and_skips_invalid_items(connector, api):
    api.get(
        API_LIST_DEVICES_URL,
        [
            {"json": {"items": [SERVER_DEVICE, {}, {"name": "no id"}], "nextAnchor": "page-2"}},
            {"json": {"items": [DESKTOP_DEVICE, MOBILE_DEVICE, RELAY_DEVICE]}},
        ],
    )

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == [
        SERVER_DEVICE["id"],
        DESKTOP_DEVICE["id"],
        MOBILE_DEVICE["id"],
        RELAY_DEVICE["id"],
    ]
    devices_requests = [r for r in api.request_history if r.method == "GET"]
    assert devices_requests[0].qs == {"limit": ["200"]}
    assert devices_requests[1].qs == {"limit": ["200"], "anchor": ["page-2"]}
    assert devices_requests[0].headers["Authorization"] == "Bearer token"
    assert connector._latest_time == "2023-05-21T10:00:00+00:00"
    connector.log.assert_any_call(
        "WithSecure device asset collection complete - 4 devices collected, skipped: "
        "1 invalid, 0 unmappable, 0 not updated since the checkpoint",
        level="info",
    )


def test_get_assets_null_items(connector, api):
    api.get(API_LIST_DEVICES_URL, json={"items": None})
    assert list(connector.get_assets()) == []


def test_checkpoint_set_before_last_device(connector, api):
    # the SDK may push the last batch, and save the checkpoint, before the generator ends
    api.get(API_LIST_DEVICES_URL, json={"items": [SERVER_DEVICE, DESKTOP_DEVICE]})

    latest_times = [connector._latest_time for _ in connector.get_assets()]

    assert latest_times == [None, "2023-05-21T10:00:00+00:00"]


def test_checkpoint_not_moved_when_stopped(connector, api, mocker):
    mocker.patch.object(
        WithSecureDeviceAssetConnector, "running", new_callable=PropertyMock, side_effect=[True, False]
    )
    api.get(API_LIST_DEVICES_URL, json={"items": [DESKTOP_DEVICE], "nextAnchor": "page-2"})

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == [DESKTOP_DEVICE["id"]]
    assert connector._latest_time is None


def test_checkpoint_skips_devices_not_updated(connector, api):
    with connector.context as cache:
        cache["most_recent_date_seen"] = "2023-05-20T13:15:16.550000+00:00"
    api.get(API_LIST_DEVICES_URL, json={"items": [SERVER_DEVICE, DESKTOP_DEVICE, MOBILE_DEVICE, RELAY_DEVICE]})

    assets = list(connector.get_assets())

    # MOBILE is older than the checkpoint; SERVER is at the checkpoint; RELAY has no timestamp
    assert [asset.device.uid for asset in assets] == [SERVER_DEVICE["id"], DESKTOP_DEVICE["id"], RELAY_DEVICE["id"]]

    connector.update_checkpoint()
    assert connector.most_recent_date_seen == "2023-05-21T10:00:00+00:00"


def test_checkpoint_unchanged_without_newer_device(connector, api):
    with connector.context as cache:
        cache["most_recent_date_seen"] = "2023-05-21T10:00:00+00:00"
    api.get(API_LIST_DEVICES_URL, json={"items": [SERVER_DEVICE, DESKTOP_DEVICE]})

    # DESKTOP is at the checkpoint and re-sent
    assert [asset.device.uid for asset in connector.get_assets()] == [DESKTOP_DEVICE["id"]]
    assert connector._latest_time is None


def test_checkpoint_not_moved_by_partial_listing(connector, api):
    api.get(
        API_LIST_DEVICES_URL,
        [
            {"json": {"items": [DESKTOP_DEVICE], "nextAnchor": "page-2"}},
            {"status_code": 400, "json": {"message": "bad anchor"}},
        ],
    )

    with pytest.raises(requests.HTTPError):
        list(connector.get_assets())

    assert connector._latest_time is None
    connector.update_checkpoint()
    assert connector.most_recent_date_seen is None
    connector.log.assert_any_call(
        "Failed to collect WithSecure devices: WithSecure API returned 'bad anchor' (status=400)", level="error"
    )


def test_reset_checkpoint(connector):
    with connector.context as cache:
        cache["most_recent_date_seen"] = "2023-05-21T10:00:00+00:00"
    connector._latest_time = "2023-05-21T10:00:00+00:00"

    connector.reset_checkpoint()

    assert connector.most_recent_date_seen is None
    assert connector._latest_time is None


def test_get_mapped_fields_mirrors_mapping_doc(connector):
    mapping = Path(__file__).parents[2] / "withsecure/asset_connector/device_mapping.yml"
    documented = {
        (source, field["target"])
        for field in yaml.safe_load(mapping.read_text())["mapping"]["fields"]
        if not field["source"].startswith("static:")
        for source in field["source"].split(", ")
    }

    fields = connector.get_mapped_fields()

    assert set(fields.items()) <= documented
    assert set(fields) == {source for source, _ in documented}


def test_get_assets_skips_unmappable_device(connector, api, mocker):
    with pytest.raises(ValidationError) as error:
        WithSecureDevice.model_validate({})
    mocker.patch.object(connector, "map_fields", side_effect=[error.value, map_device(connector, DESKTOP_DEVICE)])
    api.get(API_LIST_DEVICES_URL, json={"items": [SERVER_DEVICE, DESKTOP_DEVICE]})

    assets = list(connector.get_assets())

    assert [asset.device.uid for asset in assets] == [DESKTOP_DEVICE["id"]]
