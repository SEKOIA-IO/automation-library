# third parties
import requests_mock

# internals
from fortigate.action_fortigate_disable_local_user import FortigateDisableLocalUserAction


def test_fortigate_disable_local_user():
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

    request_return = {
        "http_method": "PUT",
        "revision": "9160554b516a09becf109e1037d0845b",
        "mkey": "test3",
        "status": "success",
        "http_status": 200,
        "vdom": "root",
        "path": "user",
        "name": "local",
        "serial": "FGVM1VTM19001555",
        "version": "v7.4.9",
        "build": 2829,
        "action": "",
        "revision_changed": True,
        "old_revision": "49eabda84a2652d2f4870df9028467d8",
    }

    mt: FortigateDisableLocalUserAction = FortigateDisableLocalUserAction()
    mt.module.configuration = firewalls

    with requests_mock.Mocker() as mock:
        for firewall in mt.module.configuration["firewalls"]:
            base_ip: str = firewall.get("base_ip")
            base_port: str = firewall.get("base_port")
            api_key: str = firewall.get("api_key")

            name: str = "sekoïa"

            mock.put(
                "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/user/local/" + name,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_return,
            )

            status: str = "disable"

            arguments = {
                "status": status,
            }
            mt.run(arguments)

            assert mock.call_count >= 1

            for cpt_mock in range(len(firewalls) - 1):
                history = mock.request_history
                assert history[cpt_mock].method == "PUT"
                assert (
                    history[cpt_mock].url
                    == "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/user/local/" + name + "/?vdom=root"
                )
                assert history[cpt_mock].json()["json"]["status"] == status
                assert history[cpt_mock].json()["json"]["name"] == name
