import requests_mock

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.alert_actions import CrowdstrikeActionCommentAlert, CrowdstrikeActionUpdateAlertStatus
from crowdstrike_falcon.host_actions import CrowdstrikeActionDeIsolateHosts


def configured_action(action: CrowdstrikeAction):
    module = CrowdStrikeFalconModule()
    a = action(module)

    a.module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "client_id": "my-client-id",
        "client_secret": "my-client-secret",
    }

    return a


def test_update_alert_status_action():
    action = configured_action(CrowdstrikeActionUpdateAlertStatus)
    ids = ["alert1", "alert2"]
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
            "PATCH",
            "https://my.fake.sekoia/alerts/entities/alerts/v3",
            json={
                "composite_ids": ids,
                "action_parameters": [
                    {
                        "name": "update_status",
                        "value": "reopened",
                    }
                ],
            },
        )

        action.run({"ids": ids, "new_status": "reopened"})

        assert mock.call_count == 2  # One call to OAUTH2 token, one call to isolate hosts


def test_comment_alert():
    action = configured_action(CrowdstrikeActionCommentAlert)
    ids = ["alert1", "alert2"]
    comment = "Hello world"
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
            "PATCH",
            "https://my.fake.sekoia/alerts/entities/alerts/v3",
            json={
                "composite_ids": ids,
                "action_parameters": [
                    {
                        "name": "append_comment",
                        "value": comment,
                    }
                ],
            },
        )

        action.run({"ids": ids, "comment": comment})

        assert mock.call_count == 2  # One call to OAUTH2 token, one call to append comment api
