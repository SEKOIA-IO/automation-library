import time

import pytest
from websocket import WebSocketTimeoutException

from retarus_modules.consumer import RetarusEventsConsumer


@pytest.fixture
def consumer(connector, queue):
    return RetarusEventsConsumer(connector.configuration, queue, connector.log, connector.log_exception)


def test_consumer_on_error(consumer, connector):
    error_message = "Oups!"
    consumer.on_error(None, Exception(error_message))
    consumer.on_error(None, WebSocketTimeoutException())

    assert connector.log.call_count == 2

    assert connector.log.call_args_list[0].kwargs["message"] == f"Websocket error: {error_message}"
    assert connector.log.call_args_list[0].kwargs["level"] == "error"

    assert connector.log.call_args_list[1].kwargs["message"] == "Websocket timed out"
    assert connector.log.call_args_list[1].kwargs["level"] == "warning"


def test_consumer_on_close(consumer, connector):
    consumer.on_close(None)
    connector.log.assert_called_once_with(message="Closing socket connection", level="info")


def test_consumer_on_message(consumer):
    assert consumer.queue.empty()

    message_str = '{"data": "foo"}'
    consumer.on_message(None, message_str)

    assert consumer.queue.get_nowait() == message_str


def test_stop_consumer(consumer):
    consumer.start()

    assert consumer.is_alive()
    assert not consumer._stop_event.is_set()

    consumer.stop()
    time.sleep(0.5)
    assert not consumer.is_alive()
    assert consumer._stop_event.is_set()
