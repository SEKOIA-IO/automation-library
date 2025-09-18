import logging
import os
import queue
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from dateutil.parser import isoparse

from gateway_cloud_services.trigger_skyhigh_security_swg import (
    EventCollector,
    EventsForwarder,
    SkyhighSecuritySWGTrigger,
    Transformer,
)

LOGGER = logging.getLogger(__name__)

EMPTY_RESPONSE = b"\n\n"


@pytest.fixture
def events_queue():
    return queue.Queue()


@pytest.fixture
def trigger(symphony_storage):
    trigger = SkyhighSecuritySWGTrigger(data_path=symphony_storage)

    trigger.module.configuration = {}
    trigger.configuration = {
        "customer_id": 1234567890,
        "account_name": "aa",
        "account_password": "aa",
        "intake_key": "aa",
        "frequency": 60,
    }

    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()

    yield trigger


@pytest.fixture
def event_collector(trigger, events_queue):
    return EventCollector(trigger, events_queue)


@pytest.fixture
def forwarder(trigger, events_queue):
    return EventsForwarder(trigger, events_queue, 500)


def test_query_api_wrong_creds(trigger, event_collector, requests_mock):
    api_response: str = '{"message": "Unauthorized","status": 401}'
    event_collector.start_date = datetime.fromtimestamp(1661251791)
    event_collector.end_date = datetime.fromtimestamp(1661287731)
    url = (
        "https://msg.mcafeesaas.com/mwg/api/reporting/forensic/1234567890"
        "?filter.requestTimestampFrom=1661251791&filter.requestTimestampTo=1661287731"
    )
    requests_mock.get(
        url,
        json=api_response,
        status_code=401,
    )
    assert event_collector.query_api() is None
    assert (
        f"Request to SkyhighSWG API to fetch {url} failed with status 401"
        ' - "{\\"message\\": \\"Unauthorized\\",\\"status\\": 401}"' in trigger.log.call_args_list[2][1]["message"]
    )


def test_query_api(event_collector, requests_mock):
    url = (
        "https://msg.mcafeesaas.com/mwg/api/reporting/forensic/1234567890"
        "?filter.requestTimestampFrom=1661251791&filter.requestTimestampTo=1661287731"
    )
    csv = b'"user_id","username"\r\n"-1","foo"'
    event_collector.start_date = datetime.fromtimestamp(1661251791)
    event_collector.end_date = datetime.fromtimestamp(1661287731)

    requests_mock.get(
        url,
        content=csv,
    )
    response = event_collector.query_api()
    assert response == csv.decode("utf-8")


def test_tranformer_with_event(trigger, events_queue):
    input_queue = queue.Queue()
    transformer = Transformer(trigger, input_queue, events_queue)

    input_queue.put('"user_id","username"\r\n"-1","foo"')
    transformer.start()
    time.sleep(0.5)
    transformer.stop()

    events = events_queue.get(block=False)
    assert events == ["user_id=-1 username=foo"]


def test_tranformer_with_no_events(trigger, events_queue):
    input_queue = queue.Queue()
    transformer = Transformer(trigger, input_queue, events_queue)

    input_queue.put('"user_id","username"')
    transformer.start()
    time.sleep(0.5)
    transformer.stop()

    assert events_queue.qsize() == 0
    assert trigger.log.called is True


def test_forwarder(trigger, forwarder, events_queue):
    events_queue.put("message")
    forwarder.start()
    time.sleep(1)
    forwarder.stop()

    assert trigger.push_events_to_intakes.called


def test_sleep_until_next_batch(event_collector):
    end_date = datetime(2023, 3, 22, 11, 50, 46, tzinfo=timezone.utc)
    difference = timedelta(seconds=20)
    now = end_date - difference

    event_collector.configuration.timedelta = 0
    event_collector.end_date = end_date

    with (
        patch("gateway_cloud_services.trigger_skyhigh_security_swg.datetime") as mock_datetime,
        patch("gateway_cloud_services.trigger_skyhigh_security_swg.sleep") as mock_sleep,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        event_collector._sleep_until_next_batch()
        mock_sleep.assert_called_with(difference.total_seconds())


def test_saving_checkpoint(event_collector, requests_mock):
    with event_collector.connector.context as cache:
        cache["most_recent_date_seen"] = None
    event_collector.trigger_activation = isoparse("2024-08-15 10:26:26.172059+00:00")
    event_collector._init_time_range()

    # for start_time = 1
    assert event_collector.start_date.isoformat() == "2024-08-15T09:25:26.172059+00:00"
    assert event_collector.end_date.isoformat() == "2024-08-15T09:26:26.172059+00:00"

    with event_collector.connector.context as cache:
        cache["most_recent_date_seen"] = "2024-08-15 10:26:26.172059+00:00"
    event_collector._init_time_range()

    assert event_collector.start_date.isoformat() == "2024-08-15T10:26:26.172059+00:00"
    assert event_collector.end_date.isoformat() == "2024-08-15T10:27:26.172059+00:00"


def log(message: str, level: str = "debug", only_sentry: bool = False, **kwargs) -> None:
    logging.info(msg=message)


def log_exception(exception: Exception, **kwargs):
    logging.exception(msg=exception)


@pytest.mark.skipif("{'customer_id', 'account_name', 'account_password'}.issubset(os.environ.keys()) == False")
def test_trigger_with_credentials(symphony_storage):
    trigger = SkyhighSecuritySWGTrigger(data_path=symphony_storage)

    trigger.log = log
    trigger.log_exception = log_exception

    trigger.push_events_to_intakes = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "frequency": 120,
        "customer_id": os.environ["customer_id"],
        "account_name": os.environ["account_name"],
        "account_password": os.environ["account_password"],
        "intake_key": "",
        "api_domain_name": os.environ["api_domain_name"],
    }
    event_collector = EventCollector(trigger)
    event_collector.start_date = event_collector.trigger_activation - timedelta(minutes=2)

    event_collector.start()

    time.sleep(5)
    trigger.stop()

    assert trigger.events_queue.qsize() > 0
