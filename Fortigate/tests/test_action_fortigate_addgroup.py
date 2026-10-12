# third parties
import pytest
import requests
import requests_mock
from pydantic import ValidationError

# internals
from fortigate.action_fortigate_add_group_address import FortigateAddGroupAddress


def test_fortigate_no_current_group():
    firewalls = {
        "firewalls": [
            {
                "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "base_ip": "31.70.249.199",
                "base_port": "4443",
            },
            {
                "api_key": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "base_ip": "31.70.249.200",
                "base_port": "4443",
            },
        ]
    }

    request_return_get = {
        "http_method": "GET",
        "revision": "110.0.175.5368212845352996165.1616569757",
        "results": [],
        "vdom": "root",
        "path": "firewall",
        "name": "addrgrp",
        "status": "success",
        "http_status": 200,
        "serial": "FGT40FTK20043139",
        "version": "v6.0.6",
        "build": 6478,
    }

    request_return_post = {
        "http_method": "POST",
        "revision": "115.0.177.5368212845352996165.1616569757",
        "status": "success",
        "http_status": 200,
        "vdom": "root",
        "path": "firewall",
        "name": "addrgrp",
        "serial": "FGT40FTK20043139",
        "version": "v6.0.6",
        "build": 6478,
    }

    mt: FortigateAddGroupAddress = FortigateAddGroupAddress()
    mt.module.configuration = firewalls

    with requests_mock.Mocker() as mock:
        for firewall in mt.module.configuration["firewalls"]:
            base_ip: str = firewall.get("base_ip")
            base_port: str = firewall.get("base_port")
            api_key: str = firewall.get("api_key")

            name: str = "Sekoia_Group"
            new_member_list: list = ["test4"]

            arguments = {"name": name, "member": new_member_list}

            mock.get(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/addrgrp/?vdom=root",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return_get,
            )

            mock.post(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/addrgrp/",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return_post,
            )

        mt.run(arguments)
        assert mock.call_count >= 1

        for cpt_mock in range(len(firewalls) - 1):
            history = mock.request_history
            assert history[cpt_mock].json()["json"]["name"] == name
            assert history[cpt_mock].json()["json"]["member"] == new_member_list


def test_fortigate_with_current_group():
    firewalls = {
        "firewalls": [
            {
                "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "base_ip": "31.70.249.199",
                "base_port": "4443",
            },
            {
                "api_key": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "base_ip": "31.70.249.200",
                "base_port": "4443",
            },
        ]
    }

    request_return_get = {
        "http_method": "GET",
        "revision": "110.0.175.5368212845352996165.1616569757",
        "results": [
            {
                "q_origin_key": "Sekoia_Group",
                "name": "Sekoia_Group",
                "uuid": "631aca96-9afd-51eb-9a86-7fec344ffc83",
                "member": [{"q_origin_key": "test4", "name": "test4"}],
                "comment": "",
                "visibility": "enable",
                "color": 0,
                "tagging": [],
                "allow-routing": "disable",
            }
        ],
        "vdom": "root",
        "path": "firewall",
        "name": "addrgrp",
        "status": "success",
        "http_status": 200,
        "serial": "FGT40FTK20043139",
        "version": "v6.0.6",
        "build": 6478,
    }

    request_return_put = {
        "http_method": "PUT",
        "revision": "202.0.171.5368212845352996165.1616569757",
        "mkey": "Sekoia_Master_Group",
        "status": "success",
        "http_status": 200,
        "vdom": "root",
        "path": "firewall",
        "name": "addrgrp",
        "serial": "FGT40FTK20043139",
        "version": "v6.0.6",
        "build": 6478,
    }

    mt: FortigateAddGroupAddress = FortigateAddGroupAddress()
    mt.module.configuration = firewalls

    with requests_mock.Mocker() as mock:
        for firewall in mt.module.configuration["firewalls"]:
            base_ip: str = firewall.get("base_ip")
            base_port: str = firewall.get("base_port")
            api_key: str = firewall.get("api_key")

            name: str = "Sekoia_Group"
            new_member_list: list = ["test4"]

            arguments = {"name": name, "member": new_member_list}

            mock.put(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/addrgrp/" + name + "/",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return_put,
            )

            mock.get(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/addrgrp/Sekoia_Group?vdom=root",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return_get,
            )

            mock.get(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/addrgrp/?vdom=root",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return_get,
            )

        mt.run(arguments)
        assert mock.call_count >= 1

        for cpt_mock in range(len(firewalls) - 1):
            history = mock.request_history
            assert history[cpt_mock].json()["json"]["name"] == name
            assert history[cpt_mock].json()["json"]["member"] == new_member_list


@pytest.mark.parametrize("arguments", [{"member": ["test4"]}, {"name": "", "member": ["test4"]}])
def test_fortigate_group_requires_name(arguments):
    mt: FortigateAddGroupAddress = FortigateAddGroupAddress()
    mt.module.configuration = {"firewalls": [{"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"}]}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            mt.run(arguments)

    assert mock.call_count == 0


BASE_URL = "https://31.70.249.199:4443/api/v2/cmdb/"


@pytest.fixture
def group_action():
    mt: FortigateAddGroupAddress = FortigateAddGroupAddress()
    mt.module.configuration = {"firewalls": [{"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"}]}
    mt.base_ip = "31.70.249.199"
    mt.base_port = "4443"
    mt.api_key = "key"
    mt.vdom = "root"
    return mt


def test_fortigate_group_merges_members_of_matching_group(group_action):
    groups = {
        "results": [
            {"name": "Other_Group", "member": [{"name": "other"}]},
            {"name": "Sekoia_Group", "member": [{"name": "existing"}]},
        ]
    }

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", json=groups)
        mock.get(f"{BASE_URL}firewall/addrgrp/Sekoia_Group", json={"results": [groups["results"][1]]})
        mock.put(f"{BASE_URL}firewall/addrgrp/Sekoia_Group/", json={})

        result = group_action.run({"name": "Sekoia_Group", "member": ["new"]})

    assert result == {"objects": [["name", "Sekoia_Group"]]}
    put_request = mock.request_history[-1]
    assert put_request.method == "PUT"
    assert put_request.headers["Authorization"] == "Bearer key"
    assert put_request.json() == {"json": {"member": [{"name": "new"}, {"name": "existing"}]}}


def test_fortigate_group_is_created_when_lookup_fails(group_action):
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", exc=requests.exceptions.ConnectTimeout)
        mock.post(f"{BASE_URL}firewall/addrgrp/", json={})

        group_action.run({"name": "Sekoia_Group", "member": ["new"]})

    post_request = mock.request_history[-1]
    assert post_request.method == "POST"
    assert post_request.json() == {"json": {"name": "Sekoia_Group", "member": [{"name": "new"}]}}
    assert [(log["level"], log["message"]) for log in group_action.logs] == [
        ("error", "Timeout session on a firewall")
    ]


@pytest.mark.parametrize(
    "results,expected",
    [
        ([{"name": "srv", "member": [{"name": "a"}]}], True),
        ([{"name": "srv", "member": []}], True),
        ([{"name": "srv", "member": [{"name": "b"}]}], False),
        ([{"name": "other", "member": [{"name": "a"}]}], False),
        ([], False),
    ],
)
def test_fortigate_group_if_exists(group_action, results, expected):
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", json={"results": results})

        assert group_action.if_exists("firewall/addrgrp/", [["name", "srv"], ["member", "a"]]) is expected


def test_fortigate_group_if_exists_returns_false_on_invalid_response(group_action):
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", text="not json")

        assert group_action.if_exists("firewall/addrgrp/", [["name", "srv"]]) is False


@pytest.mark.parametrize("method,http_method", [("add_api", "POST"), ("get_api", "GET"), ("set_api", "PUT")])
def test_fortigate_group_api_returns_response(group_action, method, http_method):
    with requests_mock.Mocker() as mock:
        mock.register_uri(http_method, f"{BASE_URL}firewall/addrgrp/", json={"status": "success"})

        response = getattr(group_action, method)("firewall/addrgrp/", {"json": {}})

    assert response.json() == {"status": "success"}
    assert mock.request_history[0].qs == {"vdom": ["root"]}


@pytest.mark.parametrize("method,http_method", [("add_api", "POST"), ("get_api", "GET"), ("set_api", "PUT")])
@pytest.mark.parametrize(
    "exc,message",
    [
        (requests.exceptions.ConnectTimeout, "Timeout session on a firewall"),
        (requests.exceptions.ConnectionError, "Impossible to add IP to the firewall"),
    ],
)
def test_fortigate_group_api_failure_returns_false(group_action, method, http_method, exc, message):
    with requests_mock.Mocker() as mock:
        mock.register_uri(http_method, f"{BASE_URL}firewall/addrgrp/", exc=exc)

        assert getattr(group_action, method)("firewall/addrgrp/") is False

    assert [(log["level"], log["message"], log["fw_ip"]) for log in group_action.logs] == [
        ("error", message, "31.70.249.199")
    ]


def test_fortigate_set_fw_address_group_updates_existing_group(group_action):
    group = {"name": "Sekoia_Group", "member": [{"name": "existing"}]}

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", json={"results": [group]})
        mock.get(f"{BASE_URL}firewall/addrgrp/Sekoia_Group", json={"results": [group]})
        mock.put(f"{BASE_URL}firewall/addrgrp/Sekoia_Group/", json={"status": "success"})

        response = group_action.set_fw_address_group("Sekoia_Group", ["new"])

    assert response.json() == {"status": "success"}
    assert mock.request_history[-1].json() == {"json": {"member": [{"name": "new"}, {"name": "existing"}]}}


def test_fortigate_set_fw_address_group_creates_missing_group(group_action):
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}firewall/addrgrp/", json={"results": []})
        mock.post(f"{BASE_URL}firewall/addrgrp/", json={"status": "success"})

        response = group_action.set_fw_address_group("Sekoia_Group", ["new"])

    assert response.json() == {"status": "success"}
    assert mock.request_history[-1].json() == {"json": {"name": "Sekoia_Group", "member": [{"name": "new"}]}}
