import json
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from confluent_kafka import TopicPartition

from sentinelone_module.deep_visibility.consumer import DeepVisibilityTrigger


@pytest.fixture
def trigger(symphony_storage):
    trigger = DeepVisibilityTrigger(data_path=symphony_storage)
    trigger.log = Mock()
    trigger.module.configuration = {"hostname": "fakehostname", "api_token": "aaaaa"}
    trigger.configuration = {
        "bootstrap_servers": "kafka:9092",
        "username": "username",
        "password": "password",
        "group_id": "consumer_group",
        "topic": "topic",
        "intake_key": "intake",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.trigger_activation: datetime = datetime.now(UTC)
    yield trigger


@pytest.fixture
def fake_assignment():
    yield [TopicPartition(partition=1, topic="topic"), TopicPartition(partition=8, topic="topic")]


def test_consumer_init(trigger, fake_assignment):
    with patch("sentinelone_module.deep_visibility.consumer.Consumer") as consumer:
        consumer.return_value.assignment.side_effect = lambda: fake_assignment

        trigger._create_kafka_consumer()

        assert consumer.return_value.subscribe.call_args.args[0] == ["topic"]
        assert (
            trigger.log.call_args.kwargs["message"]
            == "DeepVisibility consumer initialized. Assigned Kafka partitions: 1, 8"
        )


def test_consumer_on_assign(trigger, fake_assignment):
    trigger._on_assign(Mock(), fake_assignment)
    assert trigger.log.call_args.kwargs["message"] == "Kafka consumer was assigned new partitions: 1, 8"


def test_consumer_on_revoke(trigger, fake_assignment):
    trigger._on_revoke(Mock(), fake_assignment)
    assert trigger.log.call_args.kwargs["message"] == "Kafka consumer was asked to revoke partitions: 1, 8"


def test_process_event(trigger, mocked_kafka_consumer):
    trigger._consumer = mocked_kafka_consumer
    trigger._log_current_lag = Mock()
    count = trigger._handle_kafka_message(last_log_at=0.0)
    assert count == 1

    events = trigger.push_events_to_intakes.call_args.kwargs["events"]

    assert len(events) == 109

    message = json.loads(events[-1])
    # Check we put the mata info in the message
    assert "meta" in message
    # Only required field for all events
    assert message["timestamp"]["millisecondsSinceEpoch"] is not None
    assert message["event_type"] == "openProcess"
    assert "source" in message
    assert "target" in message
