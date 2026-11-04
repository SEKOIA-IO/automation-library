# third parties
import requests_mock

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
