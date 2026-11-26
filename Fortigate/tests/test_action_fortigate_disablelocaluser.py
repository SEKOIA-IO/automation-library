# third parties
import pytest
import requests
import requests_mock
from pydantic import ValidationError

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
                "name": name,
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


@pytest.mark.parametrize("arguments", [{}, {"name": ""}])
def test_fortigate_disable_local_user_requires_name(arguments):
    mt: FortigateDisableLocalUserAction = FortigateDisableLocalUserAction()
    mt.module.configuration = {"firewalls": [{"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"}]}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            mt.run(arguments)

    assert mock.call_count == 0


def test_fortigate_disable_local_user_logs_error_and_continues(monkeypatch):
    mt: FortigateDisableLocalUserAction = FortigateDisableLocalUserAction()
    mt.module.configuration = {
        "firewalls": [
            {"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"},
            {"api_key": "key", "base_ip": "31.70.249.200", "base_port": "4443"},
        ]
    }
    exceptions: list = []
    monkeypatch.setattr(mt, "log_exception", lambda exception, **kwargs: exceptions.append((exception, kwargs)))

    with requests_mock.Mocker() as mock:
        mock.put("https://31.70.249.199:4443/api/v2/cmdb/user/local/john", status_code=404)
        mock.put("https://31.70.249.200:4443/api/v2/cmdb/user/local/john", json={})

        mt.run({"name": "john"})

    assert mock.call_count == 2
    assert len(exceptions) == 1
    error, kwargs = exceptions[0]
    assert isinstance(error, requests.exceptions.HTTPError)
    assert kwargs == {"message": "Impossible to disable the local user account on the firewall"}
    assert [log["message"] for log in mt.logs] == [
        "Successfully disabled the local user account john on the firewall 31.70.249.200"
    ]


def test_fortigate_disable_local_user_logs_timeout_and_continues(monkeypatch):
    mt: FortigateDisableLocalUserAction = FortigateDisableLocalUserAction()
    mt.module.configuration = {
        "firewalls": [
            {"api_key": "key", "base_ip": "31.70.249.199", "base_port": "4443"},
            {"api_key": "key", "base_ip": "31.70.249.200", "base_port": "4443"},
        ]
    }
    exceptions: list = []
    monkeypatch.setattr(mt, "log_exception", lambda exception, **kwargs: exceptions.append((exception, kwargs)))

    with requests_mock.Mocker() as mock:
        mock.put("https://31.70.249.199:4443/api/v2/cmdb/user/local/john", exc=requests.exceptions.Timeout)
        mock.put("https://31.70.249.200:4443/api/v2/cmdb/user/local/john", json={})

        mt.run({"name": "john"})

    assert mock.call_count == 2
    assert len(exceptions) == 1
    error, kwargs = exceptions[0]
    assert isinstance(error, requests.exceptions.Timeout)
    assert kwargs == {"message": "Time out session on firewall 31.70.249.199"}
    assert [log["message"] for log in mt.logs] == [
        "Successfully disabled the local user account john on the firewall 31.70.249.200"
    ]
