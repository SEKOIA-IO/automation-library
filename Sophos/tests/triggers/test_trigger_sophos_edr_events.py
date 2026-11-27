import json
import logging
from unittest.mock import Mock

import pytest
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.triggers.trigger_sophos_edr_events import SophosEDREventsTrigger

API_HOST = "https://api-eu.central.sophos.com"
DATA_REGION = "https://api-eu02.central.sophos.com"
SIEM_URL = f"{DATA_REGION}/siem/v1/events"

EVENT_REGISTERED = {
    "when": "2019-04-01T15:11:09.759Z",
    "id": "cbaff14f-a36b-46bd-8e83-6017ad79cdef",
    "customer_id": "816f36ee-dd2e-4ccd-bb12-cea766c28ade",
    "severity": "low",
    "created_at": "2019-04-01T15:11:09.984Z",
    "source_info": {"ip": "10.1.39.32"},
    "endpoint_type": "server",
    "endpoint_id": "c80c2a87-42f2-49b2-bab7-5031b69cd83e",
    "origin": None,
    "type": "Event::Endpoint::Registered",
    "location": "mock_Mercury_1",
    "source": "n/a",
    "group": "PROTECTION",
    "name": "New server registered: mock_Mercury_1",
}
EVENT_MALWARE = {
    **EVENT_REGISTERED,
    "id": "5bc48f19-3905-4f72-9f79-cd381c8e92ce",
    "severity": "medium",
    "when": "2019-04-01T15:11:41.000Z",
    "created_at": "2019-04-01T15:11:41.053Z",
    "type": "Event::Endpoint::Threat::Detected",
    "group": "MALWARE",
    "name": "Malware detected: 'Eicar-AV-Test' at 'C:\\Program Files (x86)\\Trojan Horse\\bin\\eicar.com'",
}


def batch(items: list[dict], has_more: bool = False, next_cursor: str | None = "cursor-1") -> dict:
    return {"has_more": has_more, "next_cursor": next_cursor, "items": items}


@pytest.fixture
def trigger(symphony_storage):
    trigger = SophosEDREventsTrigger(module=SophosModule(), data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": API_HOST,
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    trigger.configuration = {"frequency": 60, "chunk_size": 1, "intake_key": "0123456789"}
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def mock_api(trigger):
    with requests_mock.Mocker() as mock:
        mock.post(
            trigger.module.configuration.oauth2_authorization_url,
            json={"access_token": "access_token", "token_type": "bearer", "expires_in": 3600},
        )
        mock.get(
            f"{API_HOST}/whoami/v1",
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {"global": "https://api.central.sophos.com", "dataRegion": DATA_REGION},
            },
        )
        yield mock


def log_levels(trigger) -> list[str]:
    return [call.kwargs.get("level") for call in trigger.log.call_args_list]


def forwarded(trigger) -> list[list[dict]]:
    return [
        [json.loads(event) for event in call.kwargs["events"]]
        for call in trigger.push_events_to_intakes.call_args_list
    ]


def siem_queries(mock) -> list[dict]:
    return [request.qs for request in mock.request_history if request.url.startswith(SIEM_URL)]


def test_forward_next_batches(trigger, mock_api):
    mock_api.get(SIEM_URL, json=batch([EVENT_REGISTERED, EVENT_MALWARE]))

    trigger.forward_next_batches()

    events = forwarded(trigger)
    assert len(events) == 1
    assert [event["id"] for event in events[0]] == [EVENT_REGISTERED["id"], EVENT_MALWARE["id"]]
    # fields translated by normalize_message, threat details extracted from the name
    assert events[0][1]["rt"] == EVENT_MALWARE["created_at"]
    assert events[0][1]["filePath"] == "C:\\Program Files (x86)\\Trojan Horse\\bin\\eicar.com"
    assert trigger.cursor == "cursor-1"


@pytest.mark.parametrize(
    "cursor, exclude_types, expected_query",
    [
        pytest.param(None, None, {"limit": ["1000"], "from_date": ["1700000000"]}, id="first-run"),
        pytest.param("abc", None, {"limit": ["1000"], "cursor": ["abc"]}, id="with-cursor"),
        pytest.param(None, [], {"limit": ["1000"], "from_date": ["1700000000"]}, id="empty-exclude-types"),
        pytest.param(
            "abc",
            ["event::endpoint::registered"],
            {"limit": ["1000"], "cursor": ["abc"], "exclude_types": ["event::endpoint::registered"]},
            id="exclude-types",
        ),
    ],
)
def test_get_next_events_parameters(trigger, mock_api, monkeypatch, cursor, exclude_types, expected_query):
    monkeypatch.setattr("time.time", lambda: 1700000300)
    trigger.configuration.exclude_types = exclude_types
    mock_api.get(SIEM_URL, json=batch([]))

    assert trigger.get_next_events(cursor) == batch([])
    assert siem_queries(mock_api) == [expected_query]


def test_get_next_events_failure(trigger, mock_api):
    mock_api.get(SIEM_URL, status_code=400, json={"message": "bad request"})

    assert trigger.get_next_events(None) is None
    assert log_levels(trigger) == ["error"]


def test_forward_next_batches_follows_pages_and_flushes_large_batches(trigger, mock_api):
    mock_api.get(
        SIEM_URL,
        [
            {"json": batch([EVENT_REGISTERED] * 1001, has_more=True, next_cursor="cursor-1")},
            {"json": batch([EVENT_MALWARE], has_more=False, next_cursor="cursor-2")},
        ],
    )

    trigger.forward_next_batches()

    # the first page exceeds the pagination limit (1000): flushed at once, then the rest
    assert [len(events) for events in forwarded(trigger)] == [1001, 1]
    assert siem_queries(mock_api)[1]["cursor"] == ["cursor-1"]
    assert trigger.cursor == "cursor-2"


@pytest.mark.parametrize(
    "response, expected_cursor",
    [
        pytest.param({"status_code": 500, "json": {}}, None, id="api-error"),
        pytest.param({"json": batch([], next_cursor=None)}, None, id="no-cursor"),
        pytest.param({"json": batch([], next_cursor="cursor-1")}, "cursor-1", id="empty-page"),
    ],
)
def test_forward_next_batches_without_events(trigger, mock_api, response, expected_cursor):
    mock_api.get(SIEM_URL, **response)

    trigger.forward_next_batches()

    trigger.push_events_to_intakes.assert_not_called()
    assert trigger.cursor == expected_cursor


def test_forward_next_batches_stops_when_the_trigger_stops(trigger, mock_api):
    trigger._stop_event.set()

    trigger.forward_next_batches()

    assert siem_queries(mock_api) == []
    trigger.push_events_to_intakes.assert_not_called()


@pytest.mark.parametrize(
    "items, expected",
    [
        pytest.param(
            [{"created_at": "2019-04-01T15:11:09Z"}, {"created_at": "2019-04-01T15:12:09.984Z"}],
            1554131529.984,
            id="with-and-without-fractional-seconds",
        ),
        pytest.param([{"when": "2019-04-01T15:11:09Z"}], 1554131469.0, id="fallback-on-when"),
        pytest.param([{"foo": "bar"}], None, id="no-parseable-field"),
    ],
)
def test_get_most_recent_timestamp_from_items(trigger, items, expected):
    assert trigger._get_most_recent_timestamp_from_items(items) == expected


def test_events_without_timestamp_are_forwarded(trigger, mock_api):
    mock_api.get(SIEM_URL, json=batch([{"id": "1", "type": "Event::Endpoint::Registered", "name": "x"}]))

    trigger.forward_next_batches()

    assert [event["id"] for event in forwarded(trigger)[0]] == ["1"]


def test_cycle_summary_goes_to_the_pod_logs_only(trigger, mock_api, caplog):
    caplog.set_level(logging.INFO)
    mock_api.get(SIEM_URL, json=batch([EVENT_REGISTERED, EVENT_MALWARE]))

    trigger.forward_next_batches()

    trigger.log.assert_not_called()
    summary = [record.getMessage() for record in caplog.records if "SIEM events collected" in record.getMessage()]
    assert len(summary) == 1
    assert "pages=1" in summary[0] and "collected=2" in summary[0] and "forwarded=2" in summary[0]


def test_api_failure_message_is_stable(trigger, mock_api):
    mock_api.get(
        SIEM_URL,
        [
            {"status_code": 503, "reason": "Service Unavailable", "json": {"requestId": "1"}},
            {"status_code": 503, "reason": "Service Unavailable", "json": {"requestId": "2"}},
        ],
    )

    trigger.get_next_events(None)
    trigger.get_next_events("cursor")

    first, second = (call.kwargs["message"] for call in trigger.log.call_args_list)
    assert (
        first
        == second
        == (
            "Failed to fetch the events from the Sophos SIEM API: status 503 - Service Unavailable"
            ". Error on the Sophos side, try again later"
        )
    )


def test_collect(trigger):
    trigger.forward_next_batches = Mock()

    trigger.collect()

    trigger.forward_next_batches.assert_called_once_with()
    assert trigger.name == "Sophos events trigger"
