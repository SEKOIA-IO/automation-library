import os
import time
from threading import Thread
from unittest.mock import MagicMock, patch
import pytest
import requests_mock
from requests import Response

from sekoiaio.triggers.intelligence import (
    FeedConsumptionTrigger,
    FeedIOCConsumptionTrigger,
)

# Test data, using fake STIX payload data as the trigger does not parse these objects
message1 = {"items": [f"STIX item {i}" for i in range(200)], "next_cursor": "abcd"}


@pytest.fixture
def trigger(data_storage):
    # Define a log function to capture log messages
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    trigger = FeedConsumptionTrigger(data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = fake_log_cb
    trigger.log_exception = MagicMock()
    trigger.send_event = MagicMock()
    trigger.module.configuration = {
        "api_key": os.environ.get("SEKOIA_API_KEY", ""),
        "base_url": "https://api.sekoia.io",
    }
    trigger.configuration = {"feed_id": "d6092c37-d8d7-45c3-8aff-c4dc26030608"}
    yield trigger


def test_url_generation(trigger):
    expected_url = (
        "https://api.sekoia.io/api/v2/inthreat/collections/"
        "d6092c37-d8d7-45c3-8aff-c4dc26030608/objects"
        "?limit=200&include_revoked=False&skip_expired=true"
    )
    assert expected_url == trigger.url


def test_url_generation_modified_after(trigger):
    trigger.configuration["modified_after"] = "2021-09-01T00:00:00Z"
    expected_url = (
        "https://api.sekoia.io/api/v2/inthreat/collections/"
        "d6092c37-d8d7-45c3-8aff-c4dc26030608/objects"
        "?limit=200&include_revoked=False&skip_expired=true&modified_after=2021-09-01T00:00:00Z"
    )
    assert expected_url == trigger.url


def test_fetch_objects(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            trigger.url,
            status_code=200,
            json=message1,
        )

        objects = trigger.fetch_objects()
        assert objects.sort() == message1["items"].sort()


def test_next_batch_with_data(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            trigger.url,
            status_code=200,
            json=message1,
        )
        trigger.next_batch()
        assert len(trigger.send_event.mock_calls) == 1


@patch("time.sleep", return_value=None)
def test_next_batch_is_empty(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            trigger.url,
            status_code=200,
            json={"items": [], "next_cursor": "abcd"},
        )

        trigger.next_batch()
        assert len(trigger.send_event.mock_calls) == 0


def test_handle_response_error(trigger):
    response = Response()
    response.status_code = 500
    response.reason = "Internal Error"
    trigger._STOP_EVENT_WAIT = 0.01
    with pytest.raises(Exception):
        trigger._handle_response_error(response)


def test_indicator_filter(data_storage):
    trigger = FeedIOCConsumptionTrigger(data_path=data_storage)
    trigger.module.configuration = {
        "api_key": os.environ.get("SEKOIA_API_KEY", ""),
        "base_url": "https://api.sekoia.io",
    }
    trigger.configuration = {"feed_id": "d6092c37-d8d7-45c3-8aff-c4dc26030608"}
    assert "match[type]=indicator" in trigger.url


@pytest.mark.skipif(
    os.environ.get("SEKOIA_API_KEY") is None,
    reason="Missing SEKOIA_API_KEY environment variable",
)
def test_run(trigger):
    main_thread = Thread(target=trigger.run)
    main_thread.start()

    # wait few seconds
    time.sleep(1)
    trigger._stop_event.set()
    main_thread.join(timeout=60)

    calls = [call.kwargs["event"] for call in trigger.send_event.call_args_list]
    assert len(calls) > 0
