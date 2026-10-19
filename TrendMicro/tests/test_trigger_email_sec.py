import time
from unittest.mock import Mock, patch

import pytest
import requests_mock

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import (
    TrendMicroConnectorConfiguration,
    TrendMicroEmailSecurityConnector,
    TrendMicroWorker,
)


@pytest.fixture
def trigger(symphony_storage, prepare_connector_mocks):
    module = TrendMicroModule()
    trigger = TrendMicroEmailSecurityConnector(module=module, data_path=symphony_storage)

    trigger = prepare_connector_mocks(trigger)
    trigger.configuration = TrendMicroConnectorConfiguration(
        service_url="api.tmes.trendmicro.eu",
        username="johndoe",
        api_key="01234556789abcdef",
        intake_key="intake_key",
    )

    trigger.send_event = Mock()

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


@pytest.mark.parametrize(
    "service_url",
    [
        "api.tmes.trendmicro.eu/",
        "http://api.tmes.trendmicro.eu/",
        "https://api.tmes.trendmicro.eu/",
    ],
)
def test_service_url_normalization(trigger, service_url):
    trigger.configuration.service_url = service_url
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    assert consumer.service_url == "https://api.tmes.trendmicro.eu"


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


@pytest.mark.parametrize(
    ("method_name", "expected_running"),
    [
        ("stop", False),
    ],
)
def test_worker_runtime_controls(trigger, method_name, expected_running):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    getattr(consumer, method_name)()

    assert consumer.running is expected_running


def test_worker_log_exception_is_forwarded(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    consumer.log_exception("boom")

    trigger.log_exception.assert_called_once_with("boom")


def test_set_recent_pushed_events_uses_existing_cache_bucket(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    event = {"mailID": "m1", "messageID": "msg1", "action": "Delivered"}
    consumer.set_recent_pushed_events([event])
    trigger.context_lock.acquire()
    with trigger.context as cache:
        cache["accepted_traffic"]["marker"] = "existing"
    trigger.context_lock.release()

    consumer.set_recent_pushed_events([event])

    trigger.context_lock.acquire()
    with trigger.context as cache:
        assert cache["accepted_traffic"]["marker"] == "existing"
        assert cache["accepted_traffic"]["recent_pushed_events"] == [consumer.get_event_metadata(event)]
    trigger.context_lock.release()


def test_iterate_through_pages_handles_next_token_and_empty_page(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    first_page_event = {"mailID": "m1", "messageID": "msg1", "action": "Delivered", "genTime": "2020-11-25T06:53:19Z"}

    with (
        patch.object(
            consumer,
            "request_logs_page",
            side_effect=[
                {"logs": [first_page_event], "nextToken": "abc%2Bdef"},
                {"logs": [], "nextToken": None},
            ],
        ) as mock_request_page,
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
        mock_time.time.return_value = 1666711174

        pages = list(consumer.iterate_through_pages(from_timestamp=0))

    assert pages == [[first_page_event]]
    assert mock_request_page.call_count == 2
    second_call_params = mock_request_page.call_args_list[1].kwargs["params"]
    assert second_call_params["token"] == "abc+def"


@pytest.mark.parametrize(
    "content",
    [
        {"logs": [{"mailID": "m1", "messageID": "msg1", "action": "Delivered"}], "nextToken": None},
    ],
)
def test_iterate_through_pages_stops_when_next_token_is_missing(trigger, content):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    with (
        patch.object(consumer, "request_logs_page", return_value=content),
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
        mock_time.time.return_value = 1666711174
        pages = list(consumer.iterate_through_pages(from_timestamp=0))

    assert pages == [content["logs"]]


def test_iterate_through_pages_exits_immediately_when_worker_is_stopped(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    consumer.stop()

    with (
        patch.object(consumer, "request_logs_page", return_value={"logs": [], "nextToken": None}),
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
        mock_time.time.return_value = 1666711174
        pages = list(consumer.iterate_through_pages(from_timestamp=0))

    assert pages == []


def test_fetch_events_skips_empty_batches(trigger):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")

    with patch.object(consumer, "iterate_through_pages", return_value=iter([[]])):
        assert list(consumer.fetch_events()) == []


def test_next_batch_does_not_update_timestamp_when_event_is_not_newer(trigger, mocked_email_worker_runtime):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    event = {"mailID": "m1", "messageID": "msg1", "action": "Delivered", "genTime": "1970-01-01T00:00:00Z"}

    mock_time = mocked_email_worker_runtime
    mock_time.time.side_effect = [100, 101, 101]

    with (
        patch.object(consumer, "fetch_events", return_value=iter([[event]])),
        patch.object(consumer, "get_last_timestamp", return_value=10),
        patch.object(consumer, "set_last_timestamp") as mock_set_last_timestamp,
    ):
        consumer.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
    mock_set_last_timestamp.assert_not_called()


def test_next_batch_sleeps_when_batch_is_empty(trigger, mocked_email_worker_runtime):
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    mock_time = mocked_email_worker_runtime
    mock_time.time.side_effect = [100, 160]

    with patch.object(consumer, "fetch_events", return_value=iter([[]])):
        consumer.next_batch()

    mock_time.sleep.assert_any_call(consumer.frequency)


def test_fetch_event(trigger, response_message, response_message_empty, mocked_email_worker_runtime):
    with requests_mock.Mocker() as mock_requests:
        mock_time = mocked_email_worker_runtime
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


def test_fetch_empty_content(trigger, response_message_empty, mocked_email_worker_runtime):
    with requests_mock.Mocker() as mock_requests:
        mock_time = mocked_email_worker_runtime
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
