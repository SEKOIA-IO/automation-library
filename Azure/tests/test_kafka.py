from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from azure_module.kafka import KafkaForwarder


@pytest.fixture
def fake_time():
    yield datetime(2022, 10, 19, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("azure_module.kafka.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_datetime


def test_produce(patch_datetime_now):
    records = ["message1", "message2"]
    topic = "topic"
    producer = KafkaForwarder()
    producer.kafka_producer = MagicMock()
    producer.kafka_topic = topic

    producer.produce(records)
    assert [call.args for call in producer.kafka_producer.produce.call_args_list] == [
        (
            topic,
            b'{"@timestamp":"2022-10-19T11:59:59+00:00","message":"message1"}',
        ),
        (
            topic,
            b'{"@timestamp":"2022-10-19T11:59:59+00:00","message":"message2"}',
        ),
    ]
