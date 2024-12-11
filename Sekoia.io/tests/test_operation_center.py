from urllib.parse import unquote as url_decoder

import pytest
import requests_mock

from sekoiaio.operation_center import GetAlert, ListAlerts, AddEventsToACase

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


def test_list_alerts_success():
    action: ListAlerts = ListAlerts()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "alerts"
    expected_response = {"items": [], "total": 0}
    arguments = {"match[entity_uuid]": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}?match[entity_uuid]=fake_uuid"


def test_get_alert_success():
    action: GetAlert = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "alerts/fake_uuid"
    expected_response = {
        "community_uuid": "string",
        "countermeasures": [],
        "updated_at": 0,
        "source": "string",
        "updated_by_type": "string",
        "stix": {},
        "comments": [],
        "updated_by": "string",
        "details": "string",
        "entity": {"uuid": "string", "name": "string"},
        "target": "string",
        "created_by": "string",
        "history": [],
        "rule": {
            "name": "string",
            "description": "string",
            "uuid": "string",
            "type": "string",
            "severity": 0,
            "pattern": "string",
        },
        "kill_chain_short_id": "string",
        "short_id": "string",
        "alert_type": {"value": "string", "category": "string"},
        "created_at": 0,
        "created_by_type": "string",
        "is_incident": False,
        "status": {"description": "string", "uuid": "string", "name": "string"},
        "event_uuids": [],
        "uuid": "string",
        "similar": 0,
        "urgency": {
            "value": 0,
            "criticity": 0,
            "severity": 0,
            "display": "string",
            "current_value": 0,
        },
    }
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_alert_missing_arg():
    action: GetAlert = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {}

    with requests_mock.Mocker() as mock:
        pytest.raises(KeyError, action.run, arguments)

        assert mock.call_count == 0

def test_add_events_to_case():
    action: AddEventsToACase = AddEventsToACase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid/events"
    expected_response = {}
    arguments = {"uuid": "fake_uuid", "event_ids": []}

    with requests_mock.Mocker() as mock:
        mock.post(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"