from typing import Any
import requests_mock
from requests import HTTPError, Response
from thehive4py.endpoints.alert import AlertEndpoint

from thehive.create_alert import TheHiveCreateAlertV5

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

ALERT: dict[str, Any] = {
    "uuid": "00000000-0000-0000-0000-000000000001",
    "short_id": "ALXXXXXXXXX",
    "urgency": {"severity": 95},
    "created_at": 1643972499,
    "title": "My test alert",
    "details": "Lorem ipsum dolor",
    "alert_type": {"category": "information-gathering", "value": "scanner"},
    "stix": {},
}

HIVE_OUTPUT = {
    "_id": "~00000001",
    "_type": "Alert",
    "_createdBy": "user@sekoia.io",
    "_createdAt": 1716817666129,
    "type": "my-alert",
    "source": "my-source",
    "sourceRef": "my-reference",
    "title": "My test alert",
    "description": "Just a description",
    "severity": 2,
    "date": 1716817665325,
    "tags": [],
    "tlp": 2,
    "pap": 2,
    "follow": True,
    "customFields": [],
    "observableCount": 0,
    "status": "New",
    "stage": "New",
    "extraData": {},
    "newDate": 1716817665357,
    "timeToDetect": 0,
}


def test_create_alert_action_success():
    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            url="https://thehive-project.org/api/v1/alert",
            status_code=200,
            json=HIVE_OUTPUT,
        )

        result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})
        assert result is not None
        assert result["title"] == ALERT["title"]


def test_create_alert_action_api_error(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert", status_code=500)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})

    assert not result
    assert mock_alert.call_count == 1


def test_create_alert_action_long_type_tlp_pap(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert", status_code=200, json=HIVE_OUTPUT)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }
    alert = {**ALERT, "alert_type": {"category": "information-gathering", "value": "a-very-long-alert-type"}}

    result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": alert, "tlp": "3", "pap": 1})

    assert result is not None
    body = mock_alert.last_request.json()
    assert body["type"] == "information-gathering"
    assert body["tlp"] == 3
    assert body["pap"] == 1


def test_create_alert_action_api_init_error(monkeypatch):
    def raise_error(*args, **kwargs):
        raise ValueError("invalid configuration")

    monkeypatch.setattr("thehive.create_alert.TheHiveApi", raise_error)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    assert action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT}) is None


def test_create_alert_action_http_error(monkeypatch):
    response = Response()
    response.status_code = 403
    response._content = b"forbidden"

    def raise_http_error(self, alert):
        raise HTTPError("403 Client Error", response=response)

    monkeypatch.setattr(AlertEndpoint, "create", raise_http_error)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    assert action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT}) is None
