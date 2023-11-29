import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import TrendMicroEmailSecurityConnector, TrendMicroWorker


@pytest.fixture
def trigger(symphony_storage):
    module = TrendMicroModule()
    trigger = TrendMicroEmailSecurityConnector(module=module, data_path=symphony_storage)

    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "service_url": "api.tmes.trendmicro.eu",
        "username": "johndoe",
        "api_key": "01234556789abcdef",
        "intake_key": "intake_key",
    }

    trigger.send_event = MagicMock()
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    return trigger


@pytest.fixture
def response_message():
    return {
        "nextToken": "Lu2XNNHim8CZpKoJEJKREJj6jpojvvROIwMK6xL+zILf8DsPpkW5W8/XhJiWH5tsJh8VrkdCIvpmJPEd71JKaUVoxTzDTU8/3RZVvYMfxzSyGIl2XYpWj9Qo+wigLGpHY4w==",
        "logs": [
            {
                "genTime": "2020-11-25T06:53:19Z",
                "timestamp": "2020-11-25T06:53:18Z",
                "deliveryTime": "2020-11-25T06:53:28Z",
                "sender": "sender@example.com",
                "direction": "in",
                "messageID": "<7bebfeb6-f035-451f-8c4f-3377ab457b07@atl1s07mta2135.xt.local>",
                "subject": "response sample",
                "size": 66390,
                "mailID": "73173f80-2e0e-46df-b2dc-a62e80167067",
                "recipient": "rcpt@example.com",
                "action": "Delivered",
                "tlsInfo": "upstreamTLS: TLS 1.2; downstreamTLS: TLS 1.2",
                "headerFrom": "header_sender@example.com",
                "headerTo": ["header_rcpt1@example.com", "header_rcpt2@example.com", "header_rcpt3@example.com"],
                "senderIP": "1.1.1.1",
                "deliveredTo": "2.2.2.2",
                "attachments": [
                    {
                        "fileName": "test1.zip",
                        "sha256": "f78960148721b59dcb563b9964a4d47e2a834a4259f46cd12db7c1cfe82ff32e",
                    },
                    {
                        "fileName": "test2.zip",
                        "sha256": "329436266f3927e89ea961e26855c8bd1f51401d92babd6627e493295376daf5",
                    },
                ],
                "embeddedUrls": ["http://example1.com", "http://example2.com"],
                "details": "250 2.0.0 Ok: queued as 3CBEFC0811",
            }
        ],
    }


@pytest.fixture
def response_message_empty():
    return b""


def test_start_consumers(trigger):
    with patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.start") as mock_start:
        consumers = trigger.start_consumers()

        assert "accepted_traffic" in consumers
        assert "blocked_traffic" in consumers
        assert mock_start.called


def test_supervise_consumers(trigger):
    with patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.start") as mock_start:
        consumers = {
            "param_set_1": Mock(**{"is_alive.return_value": False, "running": True}),
            "param_set_2": None,
            "param_set_3": Mock(**{"is_alive.return_value": True, "running": True}),
            "param_set_4": Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers)
        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    with patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.start") as mock_start:
        consumers = {
            "param_set_1": Mock(**{"is_alive.return_value": False}),
            "param_set_2": None,
            "param_set_3": Mock(**{"is_alive.return_value": False}),
            "param_set_4": Mock(**{"is_alive.return_value": True}),
        }

        trigger.stop_consumers(consumers)

        offline_consumer = consumers.get("param_set_4")
        assert offline_consumer is not None
        assert offline_consumer.stop.called


def test_saving_checkpoint(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    now = int(time.time())

    result = consumer.get_last_timestamp()
    assert now - result <= 5 * 60 + 5

    consumer.set_last_timestamp(last_timestamp=now)

    result = consumer.get_last_timestamp()
    assert result == now

    consumer.set_last_timestamp(last_timestamp=0)
    result = consumer.get_last_timestamp()
    assert result > 0


def test_fetch_event(trigger, response_message, response_message_empty):
    with requests_mock.Mocker() as mock_requests, patch(
        "trendmicro_modules.trigger_email_sec.TrendMicroWorker.get_last_timestamp",
        return_value=0,
    ) as mock_get_ts, patch(
        "trendmicro_modules.trigger_email_sec.TrendMicroWorker.set_last_timestamp"
    ) as mock_set_ts, patch(
        "trendmicro_modules.trigger_email_sec.time"
    ) as mock_time:
        mock_requests.get(
            "https://api.tmes.trendmicro.eu/api/v1/log/mailtrackinglog",
            [{"status_code": 200, "json": response_message}, {"status_code": 200, "content": response_message_empty}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [
            start_time,  # 1st batch start
            start_time,  # 1st iterate_through_pages
            start_time,  # 1st events lag measurement
            end_time,  # 1st batch end
            end_time,  # 2nd batch start
            end_time,  # 2nd iterate_through_pages
            end_time + batch_duration,  # 2nd batch start
        ]

        consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
        consumer.next_batch()
        mock_time.sleep.assert_called_once_with(44)
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1


def test_fetch_empty_content(trigger, response_message_empty):
    with requests_mock.Mocker() as mock_requests, patch(
        "trendmicro_modules.trigger_email_sec.TrendMicroWorker.get_last_timestamp",
        return_value=0,
    ) as mock_get_ts, patch(
        "trendmicro_modules.trigger_email_sec.TrendMicroWorker.set_last_timestamp"
    ) as mock_set_ts, patch(
        "trendmicro_modules.trigger_email_sec.time"
    ) as mock_time:
        mock_requests.get(
            "https://api.tmes.trendmicro.eu/api/v1/log/mailtrackinglog",
            [{"status_code": 204, "content": response_message_empty}],
        )

        batch_duration = 60  # because we sleep after receiving no content
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, start_time, end_time]

        consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(60)
