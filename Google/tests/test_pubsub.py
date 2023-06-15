import queue
import time
from datetime import datetime
from threading import Thread
from unittest.mock import Mock, patch

from google.cloud import pubsub_v1
from google.protobuf.timestamp_pb2 import Timestamp
from pytest import fixture

from google_module.pubsub import EventsForwarder, MessagesConsumer, PubSub, Worker


@fixture
def events_queue():
    return queue.Queue()


@fixture
def trigger(credentials):
    trigger = PubSub()
    trigger.module._configuration = dict(credentials=credentials)
    trigger.configuration = {
        "project_id": "project_id",
        "subject_id": "subject_id",
        "intake_key": "ïntake_key",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    yield trigger


@fixture
def consumer(trigger, events_queue):
    yield MessagesConsumer(trigger, "subscription_name", events_queue)


@fixture
def forwarder(trigger, events_queue):
    return EventsForwarder(trigger, events_queue, 500)


def test_configuration(trigger):
    assert trigger.CREDENTIALS_PATH.exists()


def create_pubsub_message(data: bytes, dt: datetime) -> pubsub_v1.types.PubsubMessage:
    timestamp = Timestamp()
    timestamp.FromDatetime(dt)
    message = pubsub_v1.types.PubsubMessage()
    message.data = data
    message.publish_time = timestamp
    return message


def create_received_message(message: pubsub_v1.types.PubsubMessage, ack_id: int) -> pubsub_v1.types.ReceivedMessage:
    received_message = pubsub_v1.types.ReceivedMessage()
    received_message.message = message
    received_message.ack_id = ack_id
    return received_message


def create_pull_response(*messages) -> pubsub_v1.types.PullResponse:
    pull_response = pubsub_v1.types.PullResponse()
    pull_response.received_messages = messages
    return pull_response


def test_fetch_events(consumer, events_queue):
    with patch("google_module.pubsub.SubscriberClient") as mock:
        instance = mock.return_value
        mock.subscription_path.return_value = "projects/13212241/subscriptions/6"
        instance.pull.return_value = create_pull_response(
            create_received_message(create_pubsub_message(b"data1", datetime(2023, 3, 11, 13, 21, 23)), "1"),
            create_received_message(create_pubsub_message(b"data2", datetime(2023, 3, 11, 13, 21, 45)), "3"),
            create_received_message(create_pubsub_message(b"data3", datetime(2023, 3, 11, 13, 45, 11)), "6"),
        )
        instance.__enter__.return_value = instance

        messages = next(consumer.fetch_events())

        assert len(messages) == 3
        assert messages == ["data1", "data2", "data3"]


def test_event_forwarder_next_batch(forwarder, events_queue):
    expected_lengths = [500, 500, 8]
    for length in expected_lengths:
        events_queue.put(list(range(length)), block=False)

    for length in expected_lengths:
        batch = forwarder.next_batch(500)
        assert len(batch) == length


def test_create_workers(trigger, events_queue):
    nb_workers = 3
    workers = trigger.create_workers(nb_workers, EventsForwarder, trigger, events_queue, 1)

    assert len(workers) == nb_workers
    for worker in workers:
        assert isinstance(worker, EventsForwarder)
        assert worker.queue == events_queue
        assert worker.max_batch_size == 1


def test_start_workers(trigger):
    worker1 = Mock()
    worker2 = Mock()
    worker3 = Mock()
    workers = [worker1, worker2, worker3]

    trigger.start_workers(workers)
    assert worker1.start.called
    assert worker2.start.called
    assert worker3.start.called


def test_stop_workers(trigger):
    worker1 = Mock()
    worker1.is_alive.return_value = True
    worker2 = Mock()
    worker2.is_alive.return_value = False
    worker3 = Mock()
    worker3.is_alive.return_value = True
    workers = [worker1, worker2, worker3]

    trigger.stop_workers(workers)
    assert worker1.stop.called
    assert not worker2.stop.called
    assert worker3.stop.called


def test_supervise_workers(trigger):
    with patch.object(Worker, "start") as mock_start:
        worker1 = Mock()
        worker1.is_alive.return_value = False
        worker2 = Mock()
        worker2.is_alive.return_value = True
        worker3 = Mock()
        worker3.is_alive.return_value = False
        workers = [worker1, worker2, worker3]

        trigger.supervise_workers(workers, Worker)
        assert mock_start.call_count == 2


def test_event_forwarder_run(trigger, forwarder, events_queue):
    batches = [["aaaaa"] * 100 for _ in range(10)]
    for batch in batches:
        events_queue.put(batch, block=False)

    events_queue.put(["aaaaa"] * 8, block=False)

    thread = Thread(target=forwarder.run)
    thread.start()
    time.sleep(1)
    forwarder.stop()
    thread.join(timeout=5)

    assert trigger.log_exception.called is False
    assert events_queue.qsize() == 0
    assert trigger.push_events_to_intakes.call_count == 3
