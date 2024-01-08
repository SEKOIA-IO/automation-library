from time import sleep
from unittest.mock import Mock

import pytest

from sekoiaio.triggers.messages_processor import MessagesProcessor


@pytest.fixture()
def callback():
    yield Mock()


def test_push_message(callback):
    processor = MessagesProcessor(callback=callback)
    processor.push_message("foo")
    assert processor._queue.qsize() == 1


def test_stop(callback):
    processor = MessagesProcessor(callback=callback)
    processor.stop()
    assert processor._stop_event.is_set() is True


def test_exit(callback):
    processor = MessagesProcessor(callback=callback)
    processor.exit(None, None)
    assert processor._stop_event.is_set() is True


def test_handle_message(callback):
    processor = MessagesProcessor(callback=callback)
    processor.push_message("foo")
    processor._handle_message()
    processor._pool.join()  # Wait for the message to be processed
    callback.assert_called_once_with("foo")


def test_run(callback):
    processor = MessagesProcessor(callback=callback)
    processor.QUEUE_TIMEOUT = 0.1
    processor.start()  # Starts the thread
    processor.push_message("foo")
    processor.stop()
    sleep(0.2)  # Give time to the thread to join the pool
    callback.assert_called_once_with("foo")
