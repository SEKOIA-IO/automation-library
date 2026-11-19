# third parties
import requests_mock

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
