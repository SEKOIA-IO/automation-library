from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from sekoia_automation.module import Module

from fastly.connector_fastly_waf import FastlyWAFConnector
from fastly.connector_fastly_waf_base import FastlyWAFConsumer


@pytest.fixture
def trigger(data_storage):
    module = Module()
    trigger = FastlyWAFConnector(module=module, data_path=data_storage)

    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "email": "john.doe@example.com",
        "token": "aaabbb",
        "corp": "testcorp",
        "site": "www.example.com",
        "intake_key": "intake_key",
        "frequency": 60,
        "chunk_size": 1,
    }
    yield trigger


@pytest.fixture
def message1():
    return {
        "totalCount": 5,
        "next": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/events?limit=1&page=2"},
        "data": [
            {
                "id": "54de69dcba53b02fbf000018",
                "timestamp": "2015-02-13T21:17:16Z",
                "source": "162.245.23.109",
                "remoteCountryCode": "AU",
                "remoteHostname": "",
                "userAgents": ["Mozilla/4.0 (compatible; MSIE 5.5; Windows NT 5.0)"],
                "action": "flagged",
                "type": "attack",
                "reasons": {"SQLI": 99},
                "requestCount": 1,
                "tagCount": 1,
                "window": 60,
                "expires": "2015-02-14T21:17:16Z",
                "expiredBy": "",
            }
        ],
    }


@pytest.fixture
def message2():
    return {
        "totalCount": 5,
        "data": [
            {
                "id": "54de69dcba53b02fbf000018",
                "timestamp": "2015-02-13T21:17:16Z",
                "source": "162.245.23.109",
                "remoteCountryCode": "AU",
                "remoteHostname": "",
                "userAgents": ["Mozilla/4.0 (compatible; MSIE 5.5; Windows NT 5.0)"],
                "action": "flagged",
                "type": "attack",
                "reasons": {"SQLI": 99},
                "requestCount": 1,
                "tagCount": 1,
                "window": 60,
                "expires": "2015-02-14T21:17:16Z",
                "expiredBy": "",
            }
        ],
    }


def test_fetch_events(trigger, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
            status_code=200,
            json=message2,
        )
        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
        )
        consumer.from_datetime = datetime(year=2022, month=2, day=24, tzinfo=timezone.utc)
        events = consumer.fetch_events()
        assert list(events) == [message2["data"]]


def test_fetch_events_with_pagination(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events?sort=asc&limit=1&from=1645660800",
            status_code=200,
            complete_qs=True,
            json=message1,
        )

        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events?limit=1&page=2",
            status_code=200,
            complete_qs=True,
            json=message2,
        )

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
        )
        consumer.from_datetime = datetime(year=2022, month=2, day=24, tzinfo=timezone.utc)
        events = consumer.fetch_events()
        assert list(events) == [message1["data"], message2["data"]]


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with patch("fastly.connector_fastly_waf_base.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
            status_code=200,
            json=message2,
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
        )
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message1, message2):
    with patch("fastly.connector_fastly_waf_base.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
            status_code=200,
            json=message2,
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/events",
        )
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0
