import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import requests
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.triggers.trigger_sophos_fusion_detections import (
    MAX_INCOMPLETE_WINDOW_RETRIES,
    MAX_RESULTS_PER_SEARCH,
    SophosFusionDetectionsTrigger,
    clean_detection,
    timestamp_to_rfc3339,
)

GRAPHQL_URL = "https://api.taegis.sophos.com/graphql"
TOKEN_URL = "https://id.sophos.com/api/v2/oauth2/token"
API_HOST = "https://api.central.sophos.com"


def detection(index: int, seconds: int = 1764238530) -> dict:
    return {
        "id": f"alert://priv:example:00000:{index}",
        "status": "OPEN",
        "attack_technique_ids": ["T1059.001"],
        "sensor_types": ["ENDPOINT"],
        "tags": [],
        "resolution_reason": None,
        "tenant": {"id": "00000", "name": "Example tenant"},
        "metadata": {
            "title": "Suspicious PowerShell command line",
            "severity": 0.6,
            "created_at": {"seconds": seconds, "nanos": 123456789},
            "ended_at": None,
            "creator": {"detector": {"detector_name": "Sophos Endpoint"}, "rule": None},
        },
        "source_entities": [
            {"id": "host-1", "perspective": "SOURCE", "properties": {"__typename": "EntityHost", "hostname": "WIN"}}
        ],
    }


def search_response(detections: list[dict], total: int | None = None, status: str = "OK") -> dict:
    return {
        "data": {
            "detectionSearch": {
                "status": status,
                "reason": "success" if status == "OK" else "failure",
                "search_id": None,
                "alerts": {
                    "total_results": len(detections) if total is None else total,
                    "list": detections,
                },
            }
        }
    }


@pytest.fixture
def trigger(symphony_storage):
    module = SophosModule()
    trigger = SophosFusionDetectionsTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": TOKEN_URL,
        "api_host": API_HOST,
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    trigger.configuration = {"frequency": 60, "chunk_size": 2, "intake_key": "0123456789"}
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def mock_api(trigger):
    with requests_mock.Mocker() as mock:
        mock.post(
            TOKEN_URL,
            json={"access_token": "access_token", "token_type": "bearer", "expires_in": 3600},
        )
        mock.get(
            f"{API_HOST}/whoami/v1",
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {"global": API_HOST, "dataRegion": "https://api-eu01.central.sophos.com"},
            },
        )
        yield mock


def forwarded_events(trigger) -> list[dict]:
    return [
        json.loads(event) for call in trigger.push_events_to_intakes.call_args_list for event in call.kwargs["events"]
    ]


def graphql_calls(mock) -> list[dict]:
    return [request.json() for request in mock.request_history if request.url == GRAPHQL_URL]


def test_timestamp_to_rfc3339():
    assert timestamp_to_rfc3339({"seconds": 1764238530, "nanos": 123456789}) == "2025-11-27T10:15:30.123Z"
    assert timestamp_to_rfc3339({"seconds": 1764238530, "nanos": 0}) == "2025-11-27T10:15:30.000Z"


def test_clean_detection_converts_timestamps_and_drops_empty_values():
    assert clean_detection(detection(1)) == {
        "id": "alert://priv:example:00000:1",
        "status": "OPEN",
        "attack_technique_ids": ["T1059.001"],
        "sensor_types": ["ENDPOINT"],
        "tenant": {"id": "00000", "name": "Example tenant"},
        "metadata": {
            "title": "Suspicious PowerShell command line",
            "severity": 0.6,
            "created_at": "2025-11-27T10:15:30.123Z",
            "creator": {"detector": {"detector_name": "Sophos Endpoint"}},
        },
        "source_entities": [
            {"id": "host-1", "perspective": "SOURCE", "properties": {"__typename": "EntityHost", "hostname": "WIN"}}
        ],
    }


def test_build_query(trigger):
    start = datetime(2026, 11, 27, 10, 0, 0, tzinfo=UTC)
    end = datetime(2026, 11, 27, 10, 5, 0, tzinfo=UTC)
    assert trigger.build_query(start, end) == (
        "from alert earliest='2026-11-27T10:00:00Z' latest='2026-11-27T10:05:00Z' | sort created_at asc"
    )

    trigger.configuration.min_severity = 0.6
    assert trigger.build_query(start, end) == (
        "from alert where severity >= 0.6 earliest='2026-11-27T10:00:00Z' latest='2026-11-27T10:05:00Z' "
        "| sort created_at asc"
    )


def test_next_batch_paginates_and_forwards(trigger, mock_api):
    mock_api.post(
        GRAPHQL_URL,
        [
            {"json": search_response([detection(1), detection(2)], total=3)},
            {"json": search_response([detection(3)], total=3)},
        ],
    )

    before = datetime.now(UTC)
    trigger.next_batch()

    events = forwarded_events(trigger)
    assert [event["id"] for event in events] == [f"alert://priv:example:00000:{index}" for index in (1, 2, 3)]
    assert events[0]["metadata"]["created_at"] == "2025-11-27T10:15:30.123Z"
    # pushed by chunks of chunk_size
    assert [len(call.kwargs["events"]) for call in trigger.push_events_to_intakes.call_args_list] == [2, 1]

    calls = graphql_calls(mock_api)
    assert [call["variables"]["in"]["offset"] for call in calls] == [0, 2]
    assert all(call["variables"]["in"]["limit"] == 2 for call in calls)
    assert calls[0]["variables"]["in"]["cql_query"].startswith("from alert earliest='")

    # the checkpoint moves to the end of the window
    assert before - timedelta(minutes=2) < trigger.cursor.offset <= datetime.now(UTC)


def test_next_batch_skips_detections_already_forwarded(trigger, mock_api):
    mock_api.post(
        GRAPHQL_URL,
        [
            {"json": search_response([detection(1)])},
            {"json": search_response([detection(1), detection(2)])},
        ],
    )

    trigger.next_batch()
    trigger.next_batch()

    assert [event["id"] for event in forwarded_events(trigger)] == [
        "alert://priv:example:00000:1",
        "alert://priv:example:00000:2",
    ]


def test_next_batch_without_detections(trigger, mock_api):
    mock_api.post(GRAPHQL_URL, json=search_response([]))

    trigger.next_batch()

    trigger.push_events_to_intakes.assert_not_called()
    assert len(graphql_calls(mock_api)) == 1


def test_next_batch_splits_large_windows(trigger, mock_api):
    trigger.configuration.chunk_size = 1000
    mock_api.post(
        GRAPHQL_URL,
        [
            {"json": search_response([detection(0)], total=MAX_RESULTS_PER_SEARCH + 1)},
            {"json": search_response([detection(1)])},
            {"json": search_response([detection(2)])},
        ],
    )

    trigger.next_batch()

    calls = graphql_calls(mock_api)
    assert len(calls) == 3
    first_window, second_window = calls[1]["variables"]["in"]["cql_query"], calls[2]["variables"]["in"]["cql_query"]
    # the second half starts where the first one ends
    assert first_window.split("latest='")[1][:20] == second_window.split("earliest='")[1][:20]
    assert [event["id"] for event in forwarded_events(trigger)] == [
        "alert://priv:example:00000:1",
        "alert://priv:example:00000:2",
    ]


def test_next_batch_cannot_split_a_one_second_window(trigger, mock_api):
    """More than 10,000 detections in one second: the first ones forwarded, loss shown, cycle moves on."""
    trigger.configuration.chunk_size = 1000
    now = datetime.now(UTC)
    trigger.cursor.offset = now - trigger.latency - timedelta(milliseconds=500) + trigger.overlap
    trigger.search = Mock(
        side_effect=lambda start, end, offset: {
            "alerts": {
                "total_results": MAX_RESULTS_PER_SEARCH + 1,
                "list": [detection(offset + index) for index in range(1000)],
            }
        }
    )

    trigger.next_batch()

    assert trigger.search.call_count == MAX_RESULTS_PER_SEARCH // 1000
    assert len(forwarded_events(trigger)) == MAX_RESULTS_PER_SEARCH
    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == [
        "More than 10000 Sophos Fusion detections in one second: only the first 10000 were collected"
    ]
    assert trigger.cursor.offset > now - trigger.latency


def empty_page_responses() -> list[dict]:
    return [
        {"json": search_response([detection(1), detection(2)], total=5)},
        {"json": search_response([], total=5)},
    ]


def test_next_batch_keeps_the_checkpoint_on_an_empty_page(trigger, mock_api):
    """An empty page before the announced total: forward what was fetched, search the window again next cycle."""
    mock_api.post(GRAPHQL_URL, empty_page_responses())
    checkpoint = trigger.cursor.offset

    trigger.next_batch()

    assert len(forwarded_events(trigger)) == 2
    assert len(graphql_calls(mock_api)) == 2
    assert trigger.cursor.offset == checkpoint
    trigger.log.assert_not_called()

    # next cycle: complete window, the detections already forwarded are skipped, the checkpoint moves
    mock_api.post(GRAPHQL_URL, json=search_response([detection(1), detection(2), detection(3)]))
    trigger.next_batch()

    assert [event["id"] for event in forwarded_events(trigger)][2:] == ["alert://priv:example:00000:3"]
    assert trigger.cursor.offset > checkpoint
    assert trigger._incomplete_window_retries == 0


def test_next_batch_moves_on_after_the_incomplete_window_retries(trigger, mock_api):
    mock_api.post(GRAPHQL_URL, empty_page_responses() * (MAX_INCOMPLETE_WINDOW_RETRIES + 1))
    checkpoint = trigger.cursor.offset

    for _ in range(MAX_INCOMPLETE_WINDOW_RETRIES):
        trigger.next_batch()
        assert trigger.cursor.offset == checkpoint
    trigger.next_batch()

    assert trigger.cursor.offset > checkpoint
    assert trigger._incomplete_window_retries == 0
    assert [call.kwargs["message"] for call in trigger.log.call_args_list] == [
        "Sophos returned fewer Sophos Fusion detections than announced: some detections may be missing"
    ]
    # forwarded once, despite the retries
    assert len(forwarded_events(trigger)) == 2


def test_next_batch_graphql_errors_keep_the_checkpoint(trigger, mock_api):
    mock_api.post(
        GRAPHQL_URL,
        json={
            "data": None,
            "errors": [
                {
                    "message": "failed to parse cql query",
                    "path": ["detectionSearch"],
                    "extensions": {"code": "BAD_USER_INPUT"},
                }
            ],
        },
    )
    checkpoint = trigger.cursor.offset

    trigger.next_batch()

    trigger.push_events_to_intakes.assert_not_called()
    assert trigger.cursor.offset == checkpoint
    error_logs = [call.kwargs["message"] for call in trigger.log.call_args_list if call.kwargs["level"] == "error"]
    assert any("BAD_USER_INPUT" in message for message in error_logs)


@pytest.mark.parametrize(
    "body, expected_code",
    [
        pytest.param(search_response([], status="ERROR"), "ERROR", id="failed-status"),
        pytest.param({"data": None}, "INCOMPLETE_RESPONSE", id="null-data"),
        pytest.param({"data": {"detectionSearch": None}}, "INCOMPLETE_RESPONSE", id="null-search"),
        pytest.param({"data": {"detectionSearch": {"status": None}}}, "INCOMPLETE_RESPONSE", id="no-status"),
        pytest.param(
            {"data": {"detectionSearch": {"status": "OK", "alerts": None}}}, "INCOMPLETE_RESPONSE", id="no-alerts"
        ),
    ],
)
def test_next_batch_incomplete_search_responses_keep_the_checkpoint(trigger, mock_api, body, expected_code):
    """Only an explicit OK with its alerts is a complete search: never an empty window by default."""
    mock_api.post(GRAPHQL_URL, json=body)
    checkpoint = trigger.cursor.offset

    trigger.next_batch()

    assert trigger.cursor.offset == checkpoint
    trigger.push_events_to_intakes.assert_not_called()
    [message] = [call.kwargs["message"] for call in trigger.log.call_args_list]
    assert message.startswith("Failed to search the Sophos Fusion detections:") and expected_code in message


def test_next_batch_http_error(trigger, mock_api):
    mock_api.post(GRAPHQL_URL, status_code=403, json={"message": "Forbidden"})

    with pytest.raises(requests.HTTPError):
        trigger.next_batch()


def test_next_batch_empty_window(trigger, mock_api):
    trigger.cursor.offset = datetime.now(UTC) + timedelta(minutes=10)

    trigger.next_batch()

    assert graphql_calls(mock_api) == []


def test_detections_without_id_are_skipped(trigger, mock_api, caplog):
    caplog.set_level(logging.INFO)
    without_id = {**detection(9), "id": None}
    mock_api.post(GRAPHQL_URL, json=search_response([without_id, detection(1)]))

    trigger.next_batch()

    assert [event["id"] for event in forwarded_events(trigger)] == ["alert://priv:example:00000:1"]
    messages = [record.getMessage() for record in caplog.records]
    assert any("Detections without id skipped" in message and "count=1" in message for message in messages)


@pytest.mark.parametrize(
    "responses, expected_pod_log",
    [
        pytest.param(
            [{"json": search_response([detection(1)])}],
            "collected=1 forwarded=1 skipped=0",
            id="summary",
        ),
        pytest.param(
            [{"json": search_response([detection(1), detection(2)], total=5)}, {"json": search_response([], total=5)}],
            "Sophos returned an empty page before the announced total",
            id="empty-page",
        ),
        pytest.param(
            [
                {"json": search_response([detection(0)], total=MAX_RESULTS_PER_SEARCH + 1)},
                {"json": search_response([])},
                {"json": search_response([])},
            ],
            "Too many detections for one search, splitting the window",
            id="window-split",
        ),
    ],
)
def test_cycle_diagnostics_go_to_the_pod_logs_only(trigger, mock_api, caplog, responses, expected_pod_log):
    caplog.set_level(logging.INFO)
    mock_api.post(GRAPHQL_URL, responses)

    trigger.next_batch()

    trigger.log.assert_not_called()
    assert any(expected_pod_log in record.getMessage() for record in caplog.records)


def test_search_errors_are_shown_with_a_stable_message(trigger, mock_api):
    error = {"message": "failed to parse cql query", "extensions": {"code": "BAD_USER_INPUT"}}
    mock_api.post(GRAPHQL_URL, json={"data": None, "errors": [error]})

    trigger.next_batch()
    trigger.next_batch()

    first, second = (call.kwargs["message"] for call in trigger.log.call_args_list)
    # no window dates in the message: the SDK deduplicates it while the error lasts
    assert first == second
    assert "earliest" not in first and "BAD_USER_INPUT" in first


def test_collect(trigger):
    trigger.next_batch = Mock()

    trigger.collect()

    trigger.next_batch.assert_called_once_with()
    assert trigger.name == "Sophos Fusion detections trigger"
