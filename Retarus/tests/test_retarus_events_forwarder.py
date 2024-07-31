import os
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
from unittest.mock import Mock

import pytest

from retarus_modules.connector import RetarusConnector


@pytest.fixture
def sample_retarus_message():
    yield '{"direction": "OUTBOUND", "class": "EVENT", "version": "1.0", "type": "MTA", "ts": "2021-05-18 16:50:30 +0200", "host": "events.retarus.com", "customer": "45987FR", "metaData": {}, "sender": "utilisateur@mail.fr", "status": "ACCEPTED", "mimeId": "<d12b9brrfd3c89723ee5@STZE007.super.corp>", "rmxId": "20210518-32464-yvrfukcZEcd-0@out33.fg", "sourceIp": "255.255.255.1", "recipient": "recepient@mail.com"}'


def test_forward_on_message(connector, queue, sample_retarus_message):
    queue.put(sample_retarus_message, block=False)
    connector.events_queue = queue

    Thread(target=connector.execute).start()
    time.sleep(2)
    connector.stop()

    assert connector.push_events_to_intakes.call_count == 1
    for call in connector.push_events_to_intakes.call_args_list:
        assert call.kwargs["events"][0] == sample_retarus_message


def test_forward_on_message_empty_queue(connector):
    Thread(target=connector.execute).start()
    time.sleep(10)
    connector.stop()

    connector.push_events_to_intakes.assert_not_called()


@pytest.mark.skipif("{'RETARUS_APIKEY'}.issubset(os.environ.keys()) == False")
def test_forward_events_integration(symphony_storage):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    trigger = RetarusConnector(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "since_time": one_hour_ago,
        "type": "message",
        "intake_key": "12345",
        "kafka_url": "bar",
        "kafka_topic": "qux",
        "ws_url": "wss://events.retarus.com/email/siem/v1/websocket?channel=testdebugsekoia",
        "ws_key": os.environ["RETARUS_APIKEY"],
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()

    thread = Thread(target=trigger.run)
    thread.start()
    time.sleep(20)
    trigger.stop()
    thread.join()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    trigger.log_exception.assert_not_called()
    assert len(calls) > 0
