import os
import time
from threading import Thread
from unittest.mock import MagicMock

import pytest
import requests_mock
from requests import Response

from sekoiaio.triggers.intelligence import (
    FeedConsumptionTrigger,
    FeedIOCConsumptionTrigger,
)

# Test data, using fake STIX payload data as the trigger does not parse these objects
feed_objects = {"items": [f"STIX item {i}" for i in range(200)], "next_cursor": "abcd"}


def object_factory(index: int, sources: list[str] | None = None):
    """
    Fixture to create a STIX object for testing.
    """
    if sources is None:
        sources = []
    return {
        "id": f"object-{index}",
        "name": f"Object {index}",
        "type": "indicator",
        "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
        "created": "2022-02-17T09:40:40.579507Z",
        "modified": "2025-05-26T12:17:29.594654Z",
        "revoked": False,
        "confidence": 50,
        "x_inthreat_sources_refs": sources,
    }


@pytest.fixture
def trigger(data_storage):
    # Define a log function to capture log messages
    def fake_log_cb(message: str, level: str):
        pass

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
    return trigger


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


def test_fetch_feed_objects(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            trigger.url,
            status_code=200,
            json=feed_objects,
        )

        objects = trigger.fetch_feed_objects()
        assert sorted(objects) == sorted(feed_objects["items"])


def test_fetch_objects(trigger):
    object1 = object_factory(1)
    object2 = object_factory(2)
    json = {"items": [object1, object2]}

    sources = ["source1", "source2"]
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            f"https://api.sekoia.io/api/v2/inthreat/objects?match[id]={','.join(sources)}",
            status_code=200,
            json=json,
        )

        objects = trigger.fetch_objects(sources)
        assert len(objects) == len(json["items"])
        assert objects == json["items"]


def test_fetch_objects_error(trigger):
    sources = ["source1", "source2"]
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            f"https://api.sekoia.io/api/v2/inthreat/objects?match[id]={','.join(sources)}", status_code=500, json={}
        )

        objects = trigger.fetch_objects(sources)
        assert objects == []


def test_resolve_sources(trigger):
    source_object1 = object_factory(1)
    source_object2 = object_factory(2)
    source_object3 = object_factory(3)
    json = {"items": [source_object1, source_object2, source_object3]}

    object1 = object_factory(1, sources=[source_object1["id"], source_object2["id"]])
    object2 = object_factory(2, sources=[source_object2["id"], source_object3["id"]])
    objects = [object1, object2]

    with requests_mock.Mocker() as mock_requests:
        sources_id = [source_object1["id"], source_object2["id"], source_object3["id"]]
        mock_requests.get(
            f"https://api.sekoia.io/api/v2/inthreat/objects?match[id]={','.join(sources_id)}",
            status_code=200,
            json=json,
        )

        objects = trigger.resolve_sources(objects)

        assert objects[0]["x_inthreat_sources"] == [
            {"name": source_object1["name"], "confidence": source_object1["confidence"]},
            {"name": source_object2["name"], "confidence": source_object2["confidence"]},
        ]
        assert objects[0]["x_inthreat_sources_refs"] == [source_object1["id"], source_object2["id"]]
        assert objects[0]["x_inthreat_sources"] == [
            {"name": source_object1["name"], "confidence": source_object1["confidence"]},
            {"name": source_object2["name"], "confidence": source_object2["confidence"]},
        ]
        assert objects[1]["x_inthreat_sources_refs"] == [source_object2["id"], source_object3["id"]]
        assert objects[1]["x_inthreat_sources"] == [
            {"name": source_object2["name"], "confidence": source_object2["confidence"]},
            {"name": source_object3["name"], "confidence": source_object3["confidence"]},
        ]
        assert trigger.sources_caches == {
            source_object1["id"]: {"name": source_object1["name"], "confidence": source_object1["confidence"]},
            source_object2["id"]: {"name": source_object2["name"], "confidence": source_object2["confidence"]},
            source_object3["id"]: {"name": source_object3["name"], "confidence": source_object3["confidence"]},
        }


def test_next_batch_with_data(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            trigger.url,
            status_code=200,
            json=feed_objects,
        )
        trigger.next_batch()
        assert len(trigger.send_event.mock_calls) == 1


def test_next_batch_is_empty(trigger, monkeypatch):
    monkeypatch.setattr("sekoiaio.triggers.intelligence.time.sleep", MagicMock())
    with trigger.context as cache:
        cache["cursors"] = {trigger.feed_id: "current-cursor"}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(trigger.url, status_code=200, json={"items": [], "next_cursor": "abcd"})
        trigger.next_batch()
        assert mock_requests.call_count == 1

    trigger.send_event.assert_not_called()
    with trigger.context as cache:
        assert cache["cursors"] == {trigger.feed_id: "current-cursor"}


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


def test_url_generation_with_stored_cursor(trigger):
    with trigger.context as cache:
        cache["cursors"] = {trigger.feed_id: "my-cursor"}
    trigger.configuration["modified_after"] = "2021-09-01T00:00:00Z"

    assert trigger.url.endswith("&skip_expired=true&cursor=my-cursor")


def test_next_batch_resolves_sources(trigger, monkeypatch):
    objects = [object_factory(1, sources=["identity--1"])]
    trigger.configuration["resolve_sources"] = True
    monkeypatch.setattr(trigger, "fetch_feed_objects", MagicMock(return_value=objects))
    monkeypatch.setattr(trigger, "resolve_sources", MagicMock(return_value=objects))
    monkeypatch.setattr("sekoiaio.triggers.intelligence.time.sleep", MagicMock())

    trigger.next_batch()

    trigger.resolve_sources.assert_called_once_with(objects)
    trigger.send_event.assert_called_once()


def test_next_batch_empty_waits_and_disables_first_run(trigger, monkeypatch):
    sleep = MagicMock()
    monkeypatch.setattr("sekoiaio.triggers.intelligence.time.sleep", sleep)
    trigger.log = MagicMock()

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(trigger.url, status_code=200, json={"items": [], "next_cursor": "abcd"})
        trigger.next_batch()

    trigger.send_event.assert_not_called()
    trigger.log.assert_any_call(message="No objects fetched from the feed", level="info")
    assert trigger.first_run is False
    sleep.assert_called_once_with(trigger.frequency)


def test_run_logs_errors_and_stops(trigger, monkeypatch):
    error = RuntimeError("boom")

    def next_batch():
        trigger._stop_event.set()
        raise error

    trigger.log = MagicMock()
    monkeypatch.setattr(trigger, "next_batch", next_batch)

    trigger.run()

    trigger.log.assert_any_call(message="Failed to get data from feed", level="error")
    trigger.log_exception.assert_called_once_with(error, message="Failed to get data from feed")
