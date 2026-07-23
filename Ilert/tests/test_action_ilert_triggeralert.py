# coding: utf-8

# third parties
import pytest
import requests_mock
from pydantic import ValidationError

# internals
from ilert.action_ilert_trigger_alert import IlertTriggerAlertAction
from ilert.constants import DEFAULT_EVENTS_URL


def test_ilert_postalert_default():
    integration_key: str = "my-fake-integration-key"

    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": integration_key}

    alert_uuid = "d41f8c20-7a9b-4e15-b6d3-92cc4a7f18e5"
    base_url = "https://api.sekoia.io/"
    api_key = "XKDF84729HNQP16"

    alert_info = {
        "urgency": {"current_value": 42, "display": "medium"},
        "short_id": "AL98312BKWZ",
        "entity": {"name": "Red fox"},
        "title": "Test alert for ilert",
        "alert_type": {"category": "network", "value": "c2-traffic"},
        "source": "172.16.0.5",
        "target": "example.org.fake",
        "details": "some details here",
        "status": {"name": "Acknowledged"},
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}v1/sic/alerts/{alert_uuid}",
            json=alert_info,
        )
        hook_url = f"{DEFAULT_EVENTS_URL}/{integration_key}"
        mock.post(hook_url, status_code=202)

        action.run({"alert_uuid": alert_uuid, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[1].method == "POST"
        assert history[1].url == hook_url
        assert history[1].json() == {**alert_info, "status": "acknowledged"}


def test_ilert_postalert_base_url_without_trailing_slash():
    integration_key: str = "my-fake-integration-key"

    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": integration_key}

    alert_uuid = "d41f8c20-7a9b-4e15-b6d3-92cc4a7f18e5"
    base_url = "https://api.sekoia.io"
    api_key = "XKDF84729HNQP16"

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}/v1/sic/alerts/{alert_uuid}",
            json={"status": {"name": "Closed"}},
        )
        mock.post(f"{DEFAULT_EVENTS_URL}/{integration_key}", status_code=202)

        action.run({"alert_uuid": alert_uuid, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
        assert mock.request_history[0].url == f"{base_url}/v1/sic/alerts/{alert_uuid}"


@pytest.mark.parametrize(
    "arguments",
    [
        {"api_key": "XKDF84729HNQP16", "base_url": "https://api.sekoia.io/"},
        {"alert_uuid": "", "api_key": "XKDF84729HNQP16", "base_url": "https://api.sekoia.io/"},
        {"alert_uuid": "   ", "api_key": "XKDF84729HNQP16", "base_url": "https://api.sekoia.io/"},
        {"alert_uuid": None, "api_key": "XKDF84729HNQP16", "base_url": "https://api.sekoia.io/"},
    ],
    ids=["missing", "empty", "blank", "none"],
)
def test_ilert_postalert_returns_none_if_alert_uuid_missing(arguments):
    integration_key: str = "my-fake-integration-key"

    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": integration_key}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run(arguments)

    assert mock.call_count == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "alert_uuid": "not-a-uuid",
            "api_key": "XKDF84729HNQP16",
            "base_url": "https://api.sekoia.io/",
        },
        {
            "alert_uuid": "d41f8c20-7a9b-4e15-b6d3-92cc4a7f18e5",
            "api_key": "XKDF84729HNQP16",
            "base_url": "not a url",
        },
    ],
    ids=["invalid-alert-uuid", "invalid-base-url"],
)
def test_ilert_postalert_rejects_invalid_argument_shapes(arguments):
    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": "my-fake-integration-key"}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run(arguments)

    assert mock.call_count == 0


def test_ilert_postalert_accepts_short_id():
    integration_key: str = "my-fake-integration-key"

    action: IlertTriggerAlertAction = IlertTriggerAlertAction()
    action.module.configuration = {"integration_key": integration_key}

    alert_short_id = "AL98312BKWZ"
    base_url = "https://api.sekoia.io/"
    api_key = "XKDF84729HNQP16"

    alert_info = {
        "urgency": {"current_value": 42, "display": "medium"},
        "short_id": alert_short_id,
        "entity": {"name": "Red fox"},
        "title": "Test alert for ilert",
        "alert_type": {"category": "network", "value": "c2-traffic"},
        "source": "172.16.0.5",
        "target": "example.org.fake",
        "details": "some details here",
        "status": {"name": "Acknowledged"},
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}v1/sic/alerts/{alert_short_id}",
            json=alert_info,
        )
        hook_url = f"{DEFAULT_EVENTS_URL}/{integration_key}"
        mock.post(hook_url, status_code=202)

        action.run({"alert_uuid": alert_short_id, "api_key": api_key, "base_url": base_url})

        assert mock.call_count == 2
