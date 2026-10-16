import json
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
from sekoia_automation.asset_connector.models.ocsf.software import (
    PackageTypeId,
    PackageTypeStr,
    SoftwareOCSFModel,
)
from sekoia_automation.module import Module

from harfanglab.asset_connector.models import HarfanglabAgent, HarfanglabApplication
from harfanglab.asset_connector.software_assets import HarfanglabSoftwareAssetConnector


@pytest.fixture
def test_software_connector(symphony_storage):
    module = Module()
    module.configuration = {
        "url": "https://example.com",
        "api_token": "fake_harfanglab_api_key",
    }

    connector = HarfanglabSoftwareAssetConnector(module=module, data_path=symphony_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    connector.log = Mock()
    connector.log_exception = Mock()

    yield connector


@pytest.fixture
def sample_agent():
    return HarfanglabAgent(
        id="3891597d-8696-4fc4-a260-b04880bdbd68",
        hostname="testhost1",
        firstseen="2025-06-11T00:15:06.454734Z",
        ostype="windows",
        osproducttype="Windows 11 Enterprise Evaluation",
        ipaddress="1.2.2.5",
        ipmask="255.255.255.0",
        domainname="TestGROUP",
    )


@pytest.fixture
def sample_application_response():
    return {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "0e8412d1-f81f-4739-b254-2879bb7bc5e5",
                "active": True,
                "installation_date": None,
                "first_seen": "2026-03-27T10:05:27.558496Z",
                "last_seen": "2026-03-27T10:06:59.416022Z",
                "first_version": "0.19051.7-0",
                "last_version": "0.19051.7-0",
                "installation_count": 1,
                "name": "YourPhone",
                "publisher": "Microsoft Corporation",
                "ostype": "windows",
                "cpe_prefix": None,
                "app_type": "uwp",
                "description": None,
            },
            {
                "id": "cec21248-77a6-4c33-b792-760f1ad3f1e2",
                "active": True,
                "installation_date": "2026-03-27T11:58:33.609974Z",
                "first_seen": "2026-03-27T10:05:27.558496Z",
                "last_seen": "2026-03-27T10:06:59.416022Z",
                "first_version": "7.2.6.172322",
                "last_version": "7.2.6.172322",
                "installation_count": 1,
                "name": "Oracle VirtualBox Guest Additions 7.2.6",
                "publisher": "Oracle and/or its affiliates",
                "ostype": "windows",
                "cpe_prefix": None,
                "app_type": "win32",
                "description": None,
            },
            {
                "id": "667d7385-bb8e-4fa0-b222-6d328d7b8836",
                "active": True,
                "installation_date": "2026-03-27T00:00:00Z",
                "first_seen": "2026-03-27T10:06:59.416022Z",
                "last_seen": "2026-03-27T10:06:59.416022Z",
                "first_version": "24.12.11",
                "last_version": "24.12.11",
                "installation_count": 1,
                "name": "HarfangLab Hurukai agent",
                "publisher": "HarfangLab",
                "ostype": "windows",
                "cpe_prefix": None,
                "app_type": "win32",
                "description": None,
            },
        ],
    }


@pytest.fixture
def sample_application():
    return HarfanglabApplication(
        id="0e8412d1-f81f-4739-b254-2879bb7bc5e5",
        name="YourPhone",
        active=True,
        first_version="0.19051.7-0",
        last_version="0.19051.7-0",
        publisher="Microsoft Corporation",
        ostype="windows",
        app_type="uwp",
    )


def test_build_software_package_uwp(test_software_connector, sample_application):
    pkg = test_software_connector.build_software_package(sample_application)

    assert pkg.name == "YourPhone"
    assert pkg.version == "0.19051.7-0"
    assert pkg.uid == "0e8412d1-f81f-4739-b254-2879bb7bc5e5"
    assert pkg.cpe_name is None
    assert pkg.type == PackageTypeStr.APPLICATION
    assert pkg.type_id == PackageTypeId.APPLICATION


def test_build_software_package_win32(test_software_connector):
    app = HarfanglabApplication(
        id="cec21248-77a6-4c33-b792-760f1ad3f1e2",
        name="Oracle VirtualBox Guest Additions 7.2.6",
        app_type="win32",
        last_version="7.2.6.172322",
        cpe_prefix="cpe:2.3:a:oracle:vm_virtualbox",
    )

    pkg = test_software_connector.build_software_package(app)

    assert pkg.name == "Oracle VirtualBox Guest Additions 7.2.6"
    assert pkg.version == "7.2.6.172322"
    assert pkg.cpe_name == "cpe:2.3:a:oracle:vm_virtualbox"
    assert pkg.type == PackageTypeStr.APPLICATION
    assert pkg.type_id == PackageTypeId.APPLICATION


def test_build_software_package_unknown_type(test_software_connector):
    app = HarfanglabApplication(
        id="test-id",
        name="SomeApp",
        app_type="custom_unknown",
        last_version="1.0",
    )

    pkg = test_software_connector.build_software_package(app)

    assert pkg.type == PackageTypeStr.UNKNOWN
    assert pkg.type_id == PackageTypeId.UNKNOWN


def test_build_software_package_no_app_type(test_software_connector):
    app = HarfanglabApplication(
        id="test-id",
        name="SomeApp",
        last_version="1.0",
    )

    pkg = test_software_connector.build_software_package(app)

    assert pkg.type == PackageTypeStr.UNKNOWN
    assert pkg.type_id == PackageTypeId.UNKNOWN


def test_build_software_package_fallback_version(test_software_connector):
    app = HarfanglabApplication(
        id="test-id",
        name="SomeApp",
        first_version="0.9",
        last_version=None,
    )

    pkg = test_software_connector.build_software_package(app)
    assert pkg.version == "0.9"


def test_build_software_package_no_version(test_software_connector):
    app = HarfanglabApplication(
        id="test-id",
        name="SomeApp",
    )

    pkg = test_software_connector.build_software_package(app)
    assert pkg.version == "unknown"


def test_build_device(test_software_connector, sample_agent):
    device = test_software_connector.build_device(sample_agent)

    assert device.uid == sample_agent.id
    assert device.hostname == "testhost1"
    assert device.domain == "TestGROUP"
    assert device.ip == "1.2.2.5"
    assert device.os.type == "windows"
    assert device.first_seen_time is not None
    assert device.type_id == 2
    assert device.type == "Desktop"


def test_map_software_fields(test_software_connector, sample_agent, sample_application):
    device = test_software_connector.build_device(sample_agent)
    software = test_software_connector.map_software_fields(sample_agent, sample_application, device)

    assert isinstance(software, SoftwareOCSFModel)
    assert software.activity_id == 2
    assert software.activity_name == "Collect"
    assert software.category_name == "Discovery"
    assert software.category_uid == 5
    assert software.class_name == "Software Inventory Info"
    assert software.class_uid == 5020
    assert software.type_name == "Software Inventory Info: Collect"
    assert software.type_uid == 502002

    # Device should be populated
    assert software.device.uid == sample_agent.id
    assert software.device.hostname == "testhost1"

    # SBOM should contain the package
    assert software.sbom is not None
    assert software.sbom.package.name == "YourPhone"
    assert software.sbom.package.version == "0.19051.7-0"

    # Metadata
    assert software.metadata.product.name == "Harfanglab EDR"
    assert software.metadata.version == "1.5.0"


def test_map_software_fields_json_serializable(test_software_connector, sample_agent, sample_application):
    device = test_software_connector.build_device(sample_agent)
    software = test_software_connector.map_software_fields(sample_agent, sample_application, device)
    json_data = software.model_dump()
    serialized = json.dumps(json_data)

    assert serialized
    assert json_data["class_uid"] == 5020
    assert json_data["sbom"]["package"]["name"] == "YourPhone"
    assert json_data["device"]["hostname"] == "testhost1"


def test_fetch_applications(test_software_connector, sample_application_response):
    agent_uid = "3891597d-8696-4fc4-a260-b04880bdbd68"

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000",
            status_code=200,
            json=sample_application_response,
        )

        apps_pages = list(test_software_connector._fetch_applications(agent_uid))

        assert len(apps_pages) == 1
        assert len(apps_pages[0]) == 3
        assert apps_pages[0][0].name == "YourPhone"
        assert apps_pages[0][1].name == "Oracle VirtualBox Guest Additions 7.2.6"
        assert apps_pages[0][2].name == "HarfangLab Hurukai agent"


def test_fetch_applications_empty(test_software_connector):
    agent_uid = "test-agent-uid"

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000",
            status_code=200,
            json={"count": 0, "next": None, "previous": None, "results": []},
        )

        apps_pages = list(test_software_connector._fetch_applications(agent_uid))

        assert len(apps_pages) == 0


def test_fetch_applications_api_error_logs_warning(test_software_connector):
    agent_uid = "test-agent-uid"

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000",
            status_code=500,
        )

        apps_pages = list(test_software_connector._fetch_applications(agent_uid))

        assert len(apps_pages) == 0
        test_software_connector.log.assert_any_call(
            f"Failed to fetch applications for agent {agent_uid}: 500 Server Error: None for url: "
            f"https://example.com/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000",
            level="warning",
        )


def test_fetch_applications_pagination(test_software_connector):
    agent_uid = "test-agent-uid"
    page1 = {
        "count": 2,
        "next": f"/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000&offset=1000",
        "previous": None,
        "results": [
            {"id": "app-1", "name": "App1", "app_type": "uwp", "last_version": "1.0"},
        ],
    }
    page2 = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": "app-2", "name": "App2", "app_type": "win32", "last_version": "2.0"},
        ],
    }

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000",
            status_code=200,
            json=page1,
        )
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/?limit=1000&offset=1000",
            status_code=200,
            json=page2,
        )

        apps_pages = list(test_software_connector._fetch_applications(agent_uid))

        assert len(apps_pages) == 2
        assert apps_pages[0][0].name == "App1"
        assert apps_pages[1][0].name == "App2"


def test_get_assets_yields_software(test_software_connector, sample_application_response):
    """Test that get_assets yields SoftwareOCSFModel for each application."""
    agent_data = {
        "id": "3891597d-8696-4fc4-a260-b04880bdbd68",
        "hostname": "testhost1",
        "firstseen": "2025-06-11T00:15:06.454734Z",
        "ostype": "windows",
        "osproducttype": "Windows 11 Enterprise Evaluation",
        "ipaddress": "1.2.2.5",
        "ipmask": "255.255.255.0",
        "domainname": "TestGROUP",
        "policy": None,
    }
    agent_endpoint_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [agent_data],
    }
    agent_uid = agent_data["id"]

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent",
            status_code=200,
            json=agent_endpoint_response,
        )
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/{agent_uid}/applications/",
            status_code=200,
            json=sample_application_response,
        )

        with patch.object(
            type(test_software_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            assets = list(test_software_connector.get_assets())

    # 3 software assets only
    assert len(assets) == 3
    assert all(isinstance(a, SoftwareOCSFModel) for a in assets)

    # All software assets reference the same device
    for sw in assets:
        assert sw.device.uid == agent_uid
        assert sw.device.hostname == "testhost1"

    # Check software names
    sw_names = {sw.sbom.package.name for sw in assets}
    assert sw_names == {"YourPhone", "Oracle VirtualBox Guest Additions 7.2.6", "HarfangLab Hurukai agent"}


def test_get_assets_software_fetch_error_continues(test_software_connector):
    """Test that a software fetch error for one agent doesn't block other agents."""
    agent1 = {
        "id": "agent-1",
        "hostname": "host1",
        "firstseen": "2025-06-11T00:15:06.454734Z",
        "ostype": "windows",
        "osproducttype": "Windows 11",
        "policy": None,
    }
    agent2 = {
        "id": "agent-2",
        "hostname": "host2",
        "firstseen": "2025-06-12T00:15:06.454734Z",
        "ostype": "windows",
        "osproducttype": "Windows 11",
        "policy": None,
    }
    agent_endpoint_response = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [agent1, agent2],
    }
    app_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {"id": "app-1", "name": "App1", "app_type": "uwp", "last_version": "1.0"},
        ],
    }

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent",
            status_code=200,
            json=agent_endpoint_response,
        )
        # agent-1 applications fail
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/agent-1/applications/",
            status_code=500,
        )
        # agent-2 applications succeed
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/agent-2/applications/",
            status_code=200,
            json=app_response,
        )

        with patch.object(
            type(test_software_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            assets = list(test_software_connector.get_assets())

    # Only agent-2's software should be yielded
    assert len(assets) == 1
    assert isinstance(assets[0], SoftwareOCSFModel)
    assert assets[0].device.uid == "agent-2"


def test_get_assets_no_applications(test_software_connector):
    """Test get_assets when agents have no applications."""
    agent_data = {
        "id": "agent-1",
        "hostname": "host1",
        "firstseen": "2025-06-11T00:15:06.454734Z",
        "ostype": "windows",
        "osproducttype": "Windows 11",
        "policy": None,
    }
    agent_endpoint_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [agent_data],
    }

    with requests_mock.Mocker() as m:
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent",
            status_code=200,
            json=agent_endpoint_response,
        )
        m.get(
            f"{test_software_connector.base_url}/api/data/endpoint/Agent/agent-1/applications/",
            status_code=200,
            json={"count": 0, "next": None, "previous": None, "results": []},
        )

        with patch.object(
            type(test_software_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: None),
        ):
            assets = list(test_software_connector.get_assets())

    assert len(assets) == 0


AGENTS_URL = "https://example.com/api/data/endpoint/Agent"


def _agent(agent_id: str, firstseen: str, **kwargs) -> dict:
    return {"id": agent_id, "hostname": f"host-{agent_id}", "firstseen": firstseen, **kwargs}


def _page(results: list, next_page: str | None = None) -> dict:
    return {"count": len(results), "next": next_page, "previous": None, "results": results}


@pytest.mark.parametrize(
    ("os_type", "expected"),
    [(None, "UNKNOWN"), ("", "UNKNOWN"), (" windows ", "WINDOWS"), ("plan9", "OTHER")],
)
def test_extract_os_type(os_type, expected):
    assert HarfanglabSoftwareAssetConnector.extract_os_type(os_type) == expected


def test_build_device_with_lastseen(test_software_connector):
    agent = HarfanglabAgent(**_agent("a1", "", lastseen="2025-06-12T00:00:00Z"))

    device = test_software_connector.build_device(agent)

    assert device.first_seen_time is None
    assert device.last_seen_time == 1749686400


def test_build_device_invalid_timestamp(test_software_connector):
    agent = HarfanglabAgent(**_agent("a1", "not-a-date"))

    device = test_software_connector.build_device(agent)

    assert device.first_seen_time is None
    assert device.last_seen_time is None
    assert any(
        c.args[0].startswith("Error parsing timestamps for asset a1") and c.kwargs == {"level": "warning"}
        for c in test_software_connector.log.call_args_list
    )


def test_most_recent_date_seen_and_update_checkpoint(test_software_connector):
    assert test_software_connector.most_recent_date_seen is None

    test_software_connector._latest_time = None
    test_software_connector.update_checkpoint()
    assert test_software_connector.most_recent_date_seen is None

    test_software_connector._latest_time = "2025-06-12T00:15:06.454735+00:00"
    test_software_connector.update_checkpoint()
    assert test_software_connector.most_recent_date_seen == "2025-06-12T00:15:06.454735+00:00"


def test_fetch_devices_paginated_with_from_date(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(
            AGENTS_URL,
            json=_page([_agent("a1", "2025-06-11T00:00:00Z")], next_page="/api/data/endpoint/Agent?offset=1"),
        )
        m.get(f"{AGENTS_URL}?offset=1", json=_page([_agent("a2", "2025-06-12T00:00:00Z"), {"hostname": "no-id"}]))

        pages = list(test_software_connector._fetch_devices(from_date="2025-06-01T00:00:00+00:00"))

        assert m.request_history[0].qs["firstseen"] == ["2025-06-01t00:00:00+00:00"]

    assert [[agent.id for agent in page] for page in pages] == [["a1"], ["a2"]]


def test_fetch_devices_no_devices(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, json={"count": 0, "results": []})

        assert list(test_software_connector._fetch_devices(from_date=None)) == []


def test_fetch_devices_stopped(test_software_connector):
    test_software_connector._stop_event.set()

    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, json=_page([_agent("a1", "2025-06-11T00:00:00Z")]))

        assert list(test_software_connector._fetch_devices(from_date=None)) == []


def test_fetch_devices_request_error(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, status_code=500)

        with pytest.raises(requests.HTTPError):
            list(test_software_connector._fetch_devices(from_date=None))


def test_fetch_applications_skips_invalid_items(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(
            f"{AGENTS_URL}/a1/applications/",
            json=_page([{"id": "app-1", "name": "App1"}, {"id": "app-2"}]),
        )

        pages = list(test_software_connector._fetch_applications("a1"))

    assert [[app.id for app in page] for page in pages] == [["app-1"]]


def test_fetch_applications_stopped(test_software_connector):
    test_software_connector._stop_event.set()

    with requests_mock.Mocker() as m:
        m.get(f"{AGENTS_URL}/a1/applications/", json=_page([{"id": "app-1", "name": "App1"}]))

        assert list(test_software_connector._fetch_applications("a1")) == []


def test_iterate_devices_keeps_most_recent_date(test_software_connector):
    test_software_connector._latest_time = None

    with requests_mock.Mocker() as m:
        m.get(
            AGENTS_URL,
            json=_page([_agent("a1", "2025-06-12T00:00:00Z")], next_page="/api/data/endpoint/Agent?offset=1"),
        )
        m.get(
            f"{AGENTS_URL}?offset=1",
            json=_page([{"hostname": "no-id"}], next_page="/api/data/endpoint/Agent?offset=2"),
        )
        m.get(f"{AGENTS_URL}?offset=2", json=_page([_agent("a0", "2025-06-11T00:00:00Z")]))

        pages = list(test_software_connector.iterate_devices())

    assert [[agent.id for agent in page] for page in pages] == [["a1"], ["a0"]]
    assert test_software_connector._latest_time == "2025-06-12T00:00:00.000001+00:00"


def test_iterate_devices_does_not_move_checkpoint_backward(test_software_connector):
    test_software_connector._latest_time = None

    with (
        requests_mock.Mocker() as m,
        patch.object(
            type(test_software_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: "2030-01-01T00:00:00+00:00"),
        ),
    ):
        m.get(AGENTS_URL, json=_page([_agent("a1", "2025-06-12T00:00:00Z")]))

        pages = list(test_software_connector.iterate_devices())

    assert len(pages) == 1
    assert test_software_connector._latest_time is None


def test_iterate_devices_error(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, status_code=500)

        with pytest.raises(requests.HTTPError):
            list(test_software_connector.iterate_devices())

    assert any(c.kwargs.get("level") == "error" for c in test_software_connector.log.call_args_list)


def test_get_assets_skips_device_build_errors(test_software_connector, monkeypatch):
    monkeypatch.setattr(test_software_connector, "build_device", Mock(side_effect=ValueError("bad device")))

    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, json=_page([_agent("a1", "2025-06-12T00:00:00Z")]))

        assert list(test_software_connector.get_assets()) == []

        # Applications are not fetched for a skipped device
        assert m.call_count == 1


def test_get_assets_skips_software_mapping_errors(test_software_connector, monkeypatch):
    monkeypatch.setattr(test_software_connector, "map_software_fields", Mock(side_effect=KeyError("bad app")))

    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, json=_page([_agent("a1", "2025-06-12T00:00:00Z")]))
        m.get(f"{AGENTS_URL}/a1/applications/", json=_page([{"id": "app-1", "name": "App1"}]))

        assert list(test_software_connector.get_assets()) == []

    test_software_connector.map_software_fields.assert_called_once()


def test_get_assets_error(test_software_connector):
    with requests_mock.Mocker() as m:
        m.get(AGENTS_URL, status_code=500)

        with pytest.raises(requests.HTTPError):
            list(test_software_connector.get_assets())

    assert test_software_connector.log.call_args_list[-1].kwargs == {"level": "error"}
    assert "Software asset generation failed" in test_software_connector.log.call_args_list[-1].args[0]
