import pytest
import requests_mock
from requests.exceptions import HTTPError

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.alert_actions import (
    CrowdstrikeActionCommentAlert,
    CrowdstrikeActionUpdateAlertStatus,
    CrowdstrikeAlertAction,
)
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


@pytest.mark.parametrize("action_class", [CrowdstrikeActionUpdateAlertStatus, CrowdstrikeActionCommentAlert])
def test_alert_action_without_ids(action_class, requests_mock):
    action = configured_action(action_class)

    action.run({"ids": [], "new_status": "closed", "comment": "Hello world"})

    assert action._error == "List of ID`s should not be empty."
    assert requests_mock.call_count == 0


def test_comment_alert_without_comment(requests_mock):
    action = configured_action(CrowdstrikeActionCommentAlert)

    with pytest.raises(ValueError, match="Comment should not be empty."):
        action.run({"ids": ["alert1"], "comment": ""})

    assert requests_mock.call_count == 0


def test_update_alert_status_with_unknown_status(requests_mock):
    action = configured_action(CrowdstrikeActionUpdateAlertStatus)

    with pytest.raises(ValueError):
        action.run({"ids": ["alert1"], "new_status": "unknown"})

    assert requests_mock.call_count == 0


def test_alert_action_requires_action_parameters():
    action = configured_action(CrowdstrikeAlertAction)

    with pytest.raises(NotImplementedError):
        action.get_action_parameters({})


def test_update_alert_status_reports_api_errors(requests_mock):
    action = configured_action(CrowdstrikeActionUpdateAlertStatus)
    requests_mock.post(
        "https://my.fake.sekoia/oauth2/token",
        json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
    )
    requests_mock.patch(
        "https://my.fake.sekoia/alerts/entities/alerts/v3",
        status_code=400,
        json={"errors": [{"code": 400, "message": "invalid composite id"}]},
    )

    with pytest.raises(HTTPError, match="invalid composite id"):
        action.run({"ids": ["alert1"], "new_status": "closed"})
