import copy
import os
import time
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import Thread
from unittest.mock import Mock

import orjson
import pytest
from websocket import WebSocketTimeoutException

from proofpoint_modules.pod.checkpoint import Checkpoint
from proofpoint_modules.trigger_pod_events import EventsForwarder, PoDEventsConsumer, PoDEventsTrigger
from tests.data import ORIGINAL_MAILLOG, ORIGINAL_MESSAGE


@pytest.mark.skipif("{'PROOFPOINT_APIKEY', 'PROOFPOINT_CLUSTER_ID'}.issubset(os.environ.keys()) == False")
def test_forward_events_integration(symphony_storage):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    trigger = PoDEventsTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "api_host": "wss://logstream.proofpoint.com/",
        "api_key": os.environ["PROOFPOINT_APIKEY"],
        "cluster_id": os.environ["PROOFPOINT_CLUSTER_ID"],
        "since_time": one_hour_ago,
        "type": "message",
        "intake_key": "12345",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()

    thread = Thread(target=trigger.run)
    thread.start()
    time.sleep(30)
    trigger.stop()
    thread.join()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    trigger.log_exception.assert_not_called
    assert len(calls) > 0


@pytest.fixture
def trigger(symphony_storage):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    trigger = PoDEventsTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "api_host": "wss://logstream.proofpoint.com/",
        "api_key": "foo",
        "cluster_id": "bar",
        "since_time": one_hour_ago,
        "type": "message",
        "intake_key": "12345",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    yield trigger


@pytest.fixture
def queue():
    return Queue()


@pytest.fixture
def checkpoint(symphony_storage):
    return Checkpoint(symphony_storage)


@pytest.fixture
def consumer(trigger, queue, checkpoint):
    return PoDEventsConsumer(trigger, queue, checkpoint)


@pytest.fixture
def forwarder(trigger, queue, checkpoint):
    return EventsForwarder(trigger, queue, checkpoint, 1)


def test_consumer_url(consumer):
    assert consumer.url.startswith("wss://logstream.proofpoint.com/v1/stream?cid=bar&type=message")


def test_consumer_on_message(consumer, queue):
    original = copy.deepcopy(ORIGINAL_MESSAGE)
    consumer.on_message(None, original)

    message = orjson.loads(original)
    assert consumer.most_recent_date_seen == message["ts"]


def test_consumer_on_error(consumer, trigger):
    consumer.on_error(None, Exception("Oups!"))
    assert trigger.log.called
    assert trigger.log.call_args_list[0].kwargs["level"] == "error"


def test_consumer_on_websocket_timeout(consumer, trigger):
    consumer.on_error(None, WebSocketTimeoutException("Ping/Pong Timed out"))
    assert trigger.log.called
    assert trigger.log.call_args_list[0].kwargs["level"] == "warning"


def test_forward_on_message(forwarder, trigger, queue):
    expected_message = orjson.loads(ORIGINAL_MESSAGE)
    message = copy.deepcopy(expected_message)

    queue.put(("2023-04-27T11:23:44+00:00", message), block=False)

    forwarder.start()
    time.sleep(0.5)
    forwarder.stop()

    expected_msg_parts = {}
    expected_urls = set()
    for msg_part in expected_message.pop("msgParts", []):
        for url in msg_part.pop("urls", []):
            expected_urls.add(url.get("url"))

        expected_msg_parts[msg_part["labeledName"]] = msg_part

    messages = []
    msg_parts = []
    urls = []
    for call in trigger.push_events_to_intakes.call_args_list:
        for serialized_event in call.kwargs["events"]:
            event = orjson.loads(serialized_event.encode("utf-8"))
            if event.get("type") == "message":
                messages.append(event)
            elif event.get("type") == "msgParts":
                msg_parts.append(event)
            elif event.get("type") == "msgPartsUrl":
                urls.append(event)

    assert len(messages) == 1
    assert messages[0] == expected_message
    assert len(msg_parts) == len(expected_msg_parts.values())
    msg_parts_uuids = set()
    for actual_msg_part in msg_parts:
        msg_parts_uuids.add(actual_msg_part.get("uuid"))
        assert actual_msg_part.get("guid") == expected_message["guid"]
        assert actual_msg_part.get("type") == "msgParts"
        content = actual_msg_part.get("msgParts", {})
        expected_msg_part = expected_msg_parts.get(content["labeledName"])
        assert expected_msg_part == content
        assert actual_msg_part.get("disposition")
    assert len(urls) == len(expected_urls)
    for actual_url in urls:
        assert actual_url.get("guid") == expected_message["guid"]
        assert actual_url.get("type") == "msgPartsUrl"
        assert actual_url.get("part_uuid") is not None
        assert actual_url["part_uuid"] in msg_parts_uuids
        assert actual_url.get("url") in expected_urls
        assert actual_url.get("disposition")


def test_pod_events_on_message_maillog(symphony_storage, queue, checkpoint):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    trigger = PoDEventsTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "api_host": "wss://logstream.proofpoint.com/",
        "api_key": "foo",
        "cluster_id": "bar",
        "since_time": one_hour_ago,
        "type": "maillog",
        "intake_key": "12345",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    forwarder = EventsForwarder(trigger, queue, checkpoint, 1)

    expected_maillog = orjson.loads(ORIGINAL_MAILLOG)
    maillog = copy.deepcopy(expected_maillog)
    queue.put(("2023-04-17T11:23:44+00:00", maillog), block=False)

    forwarder.start()
    time.sleep(0.5)
    forwarder.stop()

    assert trigger.push_events_to_intakes.called
    assert not trigger.log_exception.called
    assert orjson.loads(trigger.push_events_to_intakes.call_args_list[0].kwargs["events"][0]) == expected_maillog


def test_event_forwarder_next_batch(forwarder, queue, checkpoint):
    expected_message = orjson.loads(ORIGINAL_MESSAGE)
    message = copy.deepcopy(expected_message)

    nb_events = 1001
    now = datetime.now(timezone.utc)
    message_date = now - timedelta(minutes=nb_events)
    for index in range(nb_events):
        queue.put(((message_date + timedelta(minutes=index + 1)).isoformat(), message), block=False)

    expected_lengths = [500, 500, 8]
    for length in expected_lengths:
        batch = forwarder.next_batch(500)
        assert len(batch) == length

    # check that the forward update the checkpoint
    assert checkpoint.offset == now
