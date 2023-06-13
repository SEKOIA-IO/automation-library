from unittest.mock import Mock

import pytest
import requests_mock

from digitalshadows_modules.trigger_searchlight_events import SearchLightTrigger
from tests.data import alerts, incidents, triage_items, trigger_events


@pytest.fixture
def trigger(symphony_storage):
    trigger = SearchLightTrigger()
    trigger.trigger_activation = "2022-03-14T11:16:14.236930Z"
    trigger.module.configuration = {
        "api_url": "https://api.searchlight.app/v1",
        "basicauth_key": "AAAAAA",
        "basicauth_secret": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "searchlight_account_id": "111111111111",
    }
    trigger.configuration = {
        "frequency": 604800,
        "tenant_id": "e49e7162-0df6-48e9-a75e-237d54871e8b",
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


def test_run_trigger(trigger):
    with requests_mock.Mocker() as mock:
        mock.get(
            url="https://api.searchlight.app/v1/triage-item-events"
            "?limit=1000"
            "&event-created-after=2022-03-14T11%3A16%3A14.236930Z"
            "&event-num-after=0",
            json=trigger_events,
        )
        mock.get(
            url="https://api.searchlight.app/v1/triage-items?limit=1000"
            "&id=fbefef9c-60fd-48b2-aab4-a3bb6b91ae16"
            "&id=fd3f179d-6846-49fa-9072-1121ca98d79a"
            "&id=b206d5e9-0024-400b-99ca-ff929e77fb53"
            "&id=630408ce-ef67-45ca-969d-6baf96e801ea",
            json=triage_items,
        )
        mock.get(
            url="https://api.searchlight.app/v1/incidents?limit=100&id=8484456&id=8484455",
            json=incidents,
        )
        mock.get(
            url="https://api.searchlight.app/v1/alerts?limit=100"
            "&id=9a292741-d4c7-4ea9-8b58-2370efafc0b0"
            "&id=b3e4f95c-9698-4c3e-9e42-bb8670a02ad4"
            "&id=45d4509e-8a2a-4594-8f2c-6c775b9533ea"
            "&id=e83fc6d8-852e-451b-8ea1-8dff62452cdf"
            "&id=a8875334-f86b-4bc9-80b2-61ee86728dff",
            json=alerts,
        )

        assert trigger._fetch_alerts() == alerts + incidents
        assert trigger.send_event.call_args_list == []


def test_get_events(trigger):
    with requests_mock.Mocker() as mock:
        mock.get(
            url="https://api.searchlight.app/v1/triage-item-events?limit=1000"
            "&event-created-after=2022-03-14T11%3A16%3A14.236930Z"
            "&event-num-after=0",
            json=trigger_events,
        )
        response = trigger.query_triage_items_events()
        assert response == trigger_events


def test_offset(trigger):
    with requests_mock.Mocker() as mock:
        mock.get(
            url="https://api.searchlight.app/v1/triage-item-events"
            "?limit=1000"
            "&event-created-after=2022-03-14T11%3A16%3A14.236930Z"
            "&event-num-after=3168",
            json={},
        )
        trigger.save_last_event_num(trigger_events)
        response = trigger.query_triage_items_events()
        assert response == {}


def test_filter_events(trigger):
    ids_of_events_type_create = trigger.filter_event_type_create(trigger_events)
    assert ids_of_events_type_create == {
        "630408ce-ef67-45ca-969d-6baf96e801ea",
        "b206d5e9-0024-400b-99ca-ff929e77fb53",
        "fbefef9c-60fd-48b2-aab4-a3bb6b91ae16",
        "fd3f179d-6846-49fa-9072-1121ca98d79a",
    }


def test_get_trigger_items(trigger):
    ids_of_events_type_create = trigger.filter_event_type_create(trigger_events)
    with requests_mock.Mocker() as mock:
        mock.get(
            url="https://api.searchlight.app/v1/triage-items"
            "?limit=1000"
            "&id=fbefef9c-60fd-48b2-aab4-a3bb6b91ae16"
            "&id=fd3f179d-6846-49fa-9072-1121ca98d79a"
            "&id=b206d5e9-0024-400b-99ca-ff929e77fb53"
            "&id=630408ce-ef67-45ca-969d-6baf96e801ea",
            json=triage_items,
        )
        response = trigger.query_api(endpoint="/triage-items", uuids=ids_of_events_type_create)
        assert response == triage_items


def test_filter_triage_items(trigger):
    alerts_uuids, incidents_uuids = trigger.filter_triage_items(triage_items)
    assert alerts_uuids == {
        "45d4509e-8a2a-4594-8f2c-6c775b9533ea",
        "9a292741-d4c7-4ea9-8b58-2370efafc0b0",
        "a8875334-f86b-4bc9-80b2-61ee86728dff",
        "b3e4f95c-9698-4c3e-9e42-bb8670a02ad4",
        "e83fc6d8-852e-451b-8ea1-8dff62452cdf",
    }
    assert incidents_uuids == {8484456, 8484455}


def test_get_incidents_and_alerts(trigger):
    with requests_mock.Mocker() as mock:
        mock.get(
            url="https://api.searchlight.app/v1/incidents?limit=100&id=8484456&id=8484455",
            json=incidents,
        )
        mock.get(
            url="https://api.searchlight.app/v1/alerts?limit=100"
            "&id=9a292741-d4c7-4ea9-8b58-2370efafc0b0"
            "&id=b3e4f95c-9698-4c3e-9e42-bb8670a02ad4"
            "&id=45d4509e-8a2a-4594-8f2c-6c775b9533ea"
            "&id=e83fc6d8-852e-451b-8ea1-8dff62452cdf"
            "&id=a8875334-f86b-4bc9-80b2-61ee86728dff",
            json=alerts,
        )
        alerts_uuids, incidents_uuids = trigger.filter_triage_items(triage_items)
        assert trigger.query_api(endpoint="/alerts", uuids=alerts_uuids, pagination_limit=100) == alerts
        assert trigger.query_api(endpoint="/incidents", uuids=incidents_uuids, pagination_limit=100) == incidents
