# third parties
import pytest
import requests
import requests_mock
from pydantic import ValidationError

# internals
from fortigate.action_fortigate_add_fqdn import FortigateAddFQDNAction


def test_fortigate_set_fqdn():
    firewalls = {
        "firewalls": [
            {
                "api_key": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyx",
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

    request_return = {
        "http_method": "POST",
        "revision": "202.0.171.5368212845352996165.1616569757",
        "mkey": "test4",
        "status": "success",
        "http_status": 200,
        "vdom": "root",
        "path": "firewall",
        "name": "address",
        "serial": "FGT40FTK20043139",
        "version": "v6.0.6",
        "build": 6478,
    }

    mt: FortigateAddFQDNAction = FortigateAddFQDNAction()
    mt.module.configuration = firewalls

    with requests_mock.Mocker() as mock:
        for firewall in mt.module.configuration["firewalls"]:
            base_ip: str = firewall.get("base_ip")
            base_port: str = firewall.get("base_port")
            api_key: str = firewall.get("api_key")

            mock.post(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/address/",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return,
            )

            name: str = "test4"
            fqdn: str = "example.domain.com"
            associated_interface: str = ""
            comment: str = ""

            arguments = {
                "name": name,
                "fqdn": fqdn,
                "associated_interface": associated_interface,
                "comment": comment,
            }
            mt.run(arguments)

            assert mock.call_count >= 1

            for cpt_mock in range(len(firewalls) - 1):
                history = mock.request_history
                assert history[cpt_mock].method == "POST"
                assert (
                    history[cpt_mock].url
                    == "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/address/?vdom=root"
                )
                assert history[cpt_mock].json()["json"]["name"] == name
                assert history[cpt_mock].json()["json"]["fqdn"] == fqdn
                assert history[cpt_mock].json()["json"]["associated-interface"] == associated_interface
                assert history[cpt_mock].json()["json"]["comment"] == comment


@pytest.mark.parametrize("arguments", [{"name": "test4"}, {"name": "test4", "fqdn": ""}])
def test_fortigate_set_fqdn_requires_fqdn(arguments):
    mt: FortigateAddFQDNAction = FortigateAddFQDNAction()
    mt.module.configuration = {"firewalls": [{"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"}]}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            mt.run(arguments)

    assert mock.call_count == 0


def test_fortigate_set_fqdn_reads_manifest_interface_argument():
    mt: FortigateAddFQDNAction = FortigateAddFQDNAction()
    mt.module.configuration = {"firewalls": [{"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"}]}

    with requests_mock.Mocker() as mock:
        mock.post("https://31.70.249.199:4443/api/v2/cmdb/firewall/address/", json={})

        mt.run({"name": "test4", "fqdn": "example.com", "associated-interface": "port1"})

    assert mock.request_history[0].json()["json"]["associated-interface"] == "port1"


@pytest.mark.parametrize(
    "mock_kwargs,message",
    [
        ({"exc": requests.exceptions.ConnectTimeout}, "Timeout session on a firewall"),
        ({"status_code": 500}, "Impossible to add IP to the firewall"),
    ],
)
def test_fortigate_set_fqdn_logs_failure_and_continues(mock_kwargs, message):
    mt: FortigateAddFQDNAction = FortigateAddFQDNAction()
    mt.module.configuration = {
        "firewalls": [
            {"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443", "vdom": "custom"},
            {"api_key": "key", "base_ip": "31.70.249.200", "base_port": "4443"},
        ]
    }

    with requests_mock.Mocker() as mock:
        mock.post("https://31.70.249.199:4443/api/v2/cmdb/firewall/address/", **mock_kwargs)
        mock.post("https://31.70.249.200:4443/api/v2/cmdb/firewall/address/", json={})

        payload = mt.run({"name": "test4", "fqdn": "example.com"})

    assert payload["json"]["fqdn"] == "example.com"
    assert mock.call_count == 2
    assert mock.request_history[0].qs == {"vdom": ["custom"]}
    assert [(log["level"], log["message"], log["fw_ip"]) for log in mt.logs] == [("error", message, "31.70.249.199")]
