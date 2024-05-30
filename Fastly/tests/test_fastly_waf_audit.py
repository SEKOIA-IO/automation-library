from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from fastly.connector_fastly_waf_audit import FastlyWAFAuditConnector
from fastly.connector_fastly_waf_base import FastlyWAFConsumer


@pytest.fixture
def trigger(data_storage):
    module = Module()
    trigger = FastlyWAFAuditConnector(module=module, data_path=data_storage)

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
def message_corpo():
    # Corp activity
    return {
        "totalCount": 1,
        "data": [
            {
                "id": "65ca37c9a1b93b54ga60bbdf",
                "eventType": "accessTokenCreated",
                "msgData": {
                    "corpName": "corpname",
                    "detailLink": "https://dashboard.signalsciences.net/corps/corpname/users/john.doe+demo@sample.com",
                    "email": "john.doe+demo@sample.com",
                    "tokenName": "Dev Audit log",
                    "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                },
                "message": "John OUTREY (john.doe+demo@sample.com) created API Access Token `Dev Audit log`",
                "attachments": [
                    {
                        "Title": "",
                        "Fields": [{"Title": "Token Name", "Value": "Dev Audit log", "Short": True}],
                        "MarkdownFields": False,
                    }
                ],
                "created": "2024-02-12T15:22:49Z",
            }
        ],
    }


@pytest.fixture
def message_site():
    # Site activity
    return {
        "totalCount": 4,
        "data": [
            {
                "id": "65cb8bd7b0a762e1af01851e",
                "eventType": "testIntegration",
                "msgData": {"integrationType": "generic"},
                "message": 'John DOE (john.doe+demo@sample.com) tested a "generic" integration',
                "attachments": [],
                "created": "2024-02-13T15:33:43Z",
            },
            {
                "id": "65cb8ae0c4489bcd85b0ce4d",
                "eventType": "loggingModeChanged",
                "msgData": {"mode": "block", "oldMode": "log"},
                "message": 'John DOE (john.doe+demo@sample.com) changed agent mode from "log" to "block"',
                "attachments": [],
                "created": "2024-02-13T15:29:36Z",
            },
            {
                "id": "65cb8adc20998c33c75b469a",
                "eventType": "loggingModeChanged",
                "msgData": {"mode": "log", "oldMode": "block"},
                "message": 'John DOE (john.doe+demo@sample.com) changed agent mode from "block" to "log"',
                "attachments": [],
                "created": "2024-02-13T15:29:32Z",
            },
            {
                "id": "65cb8a386af260edn88be7f7",
                "eventType": "createIntegration",
                "msgData": {"integrationType": "generic", "plainSubscribedTo": '"all events"'},
                "message": 'John DOE (john.doe+demo@sample.com) created a new "generic" integration subscribed to "all events"',
                "attachments": [],
                "created": "2024-02-13T15:26:48Z",
            },
        ],
    }


@pytest.fixture
def message_sites():
    return {
        "data": [
            {
                "name": "www.example.com",
                "displayName": "My Website",
                "agentLevel": "block",
                "blockHTTPCode": 406,
                "blockDurationSeconds": 86400,
                "created": "2014-12-09T10:43:54-08:00",
                "whitelist": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/whitelist"},
                "blacklist": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/blacklist"},
                "events": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/events"},
                "requests": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/requests"},
                "redactions": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/redactions"},
                "suspiciousIPs": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/suspiciousIPs"},
                "monitors": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/monitors"},
                "integrations": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/integrations"},
                "headerLinks": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/headerLinks"},
                "agents": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/agents"},
                "alerts": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/alerts"},
                "analyticsEvents": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/analytics/events"},
                "topAttacks": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/top/attacks"},
                "members": {"uri": "/api/v0/corps/testcorp/sites/www.example.com/members"},
            }
        ]
    }


def test_fetch_corp_events(trigger, message_corpo):
    trigger.configuration.site = None
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/activity?sort=asc&limit=1&from=1645660800",
            status_code=200,
            json=message_corpo,
        )
        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="corp:testcorp",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/activity",
        )
        consumer.from_datetime = datetime(year=2022, month=2, day=24, tzinfo=timezone.utc)
        events = consumer.fetch_events()
        assert list(events) == [message_corpo["data"]]


def test_fetch_site_events(trigger, message_site):
    trigger.configuration.site = "www.example.com"
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
            status_code=200,
            json=message_site,
        )
        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
        )
        consumer.from_datetime = datetime(year=2022, month=2, day=24, tzinfo=timezone.utc)
        events = consumer.fetch_events()
        assert list(events) == [message_site["data"]]


def test_next_batch_sleep_until_next_round(trigger, message_corpo, message_site):
    trigger.configuration.site = "www.example.com"
    with patch("fastly.connector_fastly_waf_base.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
            status_code=200,
            json=message_site,
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
        )
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message_corpo, message_site):
    trigger.configuration.site = "www.example.com"
    with patch("fastly.connector_fastly_waf_base.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
            status_code=200,
            json=message_site,
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
        )
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_load_without_cursor(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_seen"] = None

    with patch("fastly.connector_fastly_waf_base.datetime.datetime") as mock_datetime:
        datetime_now = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        datetime_expected = datetime_now - timedelta(minutes=1)

        mock_datetime.now.return_value = datetime_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        consumer = FastlyWAFConsumer(
            connector=trigger,
            name="site:www.example.com",
            url="https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites/www.example.com/activity",
        )
        assert consumer.most_recent_date_seen.isoformat() == datetime_expected.isoformat()


def test_get_sites(trigger, message_sites):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://dashboard.signalsciences.net/api/v0/corps/testcorp/sites",
            status_code=200,
            json=message_sites,
        )

        result = trigger.get_sites()
        assert len(result) == 1
