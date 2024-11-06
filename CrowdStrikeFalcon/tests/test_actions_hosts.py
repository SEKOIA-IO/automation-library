import requests_mock

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.host_actions import CrowdstrikeActionDeIsolateHosts, CrowdstrikeActionIsolateHosts


def configured_action(action: CrowdstrikeAction):
    module = CrowdStrikeFalconModule()
    a = action(module)

    a.module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "client_id": "my-client-id",
        "client_secret": "my-client-secret",
    }

    return a


def test_isolate_hosts_action():
    action = configured_action(CrowdstrikeActionIsolateHosts)
    ids = ["host1", "host2"]
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/devices/entities/devices-actions/v2?action_name=contain",
            complete_qs=True,
            json={"ids": ids},
        )

        action.run({"ids": ids})

        history = mock.request_history
        assert mock.call_count == 2  # One call to OAUTH2 token, one call to isolate hosts
        assert "action_name=contain" in history[1].url


def test_deisolate_hosts_action():
    action = configured_action(CrowdstrikeActionDeIsolateHosts)
    ids = ["host1", "host2"]
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/devices/entities/devices-actions/v2?action_name=lift_containment",
            complete_qs=True,
            json={"ids": ids},
        )

        action.run({"ids": ids})

        history = mock.request_history
        assert mock.call_count == 2  # One call to OAUTH2 token, one call to isolate hosts
        assert "action_name=lift_containment" in history[1].url
