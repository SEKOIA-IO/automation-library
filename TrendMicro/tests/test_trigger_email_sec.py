import time
from unittest.mock import MagicMock, Mock, patch

import orjson
import pytest
import requests_mock

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.helpers import unixtime_to_iso8601
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


def test_service_url_normalization(trigger):
    # Without schema and with trailing slash
    trigger.configuration.service_url = "api.tmes.trendmicro.eu/"
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    assert consumer.service_url == "https://api.tmes.trendmicro.eu"

    # With incorrect schema and with trailing slash
    trigger.configuration.service_url = "http://api.tmes.trendmicro.eu/"
    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    assert consumer.service_url == "https://api.tmes.trendmicro.eu"

    # With correct schema and with trailing slash
    trigger.configuration.service_url = "https://api.tmes.trendmicro.eu/"
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


def test_fetch_event(trigger, response_message, response_message_empty):
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "trendmicro_modules.trigger_email_sec.TrendMicroWorker.get_last_timestamp",
            return_value=0,
        ) as mock_get_ts,
        patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.set_last_timestamp") as mock_set_ts,
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
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
    with (
        requests_mock.Mocker() as mock_requests,
        patch(
            "trendmicro_modules.trigger_email_sec.TrendMicroWorker.get_last_timestamp",
            return_value=0,
        ) as mock_get_ts,
        patch("trendmicro_modules.trigger_email_sec.TrendMicroWorker.set_last_timestamp") as mock_set_ts,
        patch("trendmicro_modules.trigger_email_sec.time") as mock_time,
    ):
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


def build_log(mail_id: str, gen_time: int) -> dict:
    return {
        "genTime": unixtime_to_iso8601(gen_time),
        "messageID": f"<{mail_id}@example.com>",
        "mailID": mail_id,
        "action": "Delivered",
        "sender": "sender@example.com",
        "recipient": "rcpt@example.com",
    }


@pytest.fixture
def paginated_responses():
    now = int(time.time())
    checkpoint = now - 3600
    max_gen_time = checkpoint + 120
    # logs are deliberately not sorted by genTime: the most recent one is on the first page
    pages = [
        {
            "nextToken": "token%2Fpage2",
            "logs": [build_log("mail-1", checkpoint + 10), build_log("mail-2", max_gen_time)],
        },
        {
            "nextToken": "token%2Fpage3",
            "logs": [build_log("mail-3", checkpoint + 20), build_log("mail-4", checkpoint + 30)],
        },
        {
            "logs": [build_log("mail-5", max_gen_time), build_log("mail-6", checkpoint + 40)],
        },
    ]
    return checkpoint, max_gen_time, pages


def test_fetch_all_pages(trigger, paginated_responses):
    checkpoint, max_gen_time, pages = paginated_responses
    url = "https://api.tmes.trendmicro.eu/api/v1/log/mailtrackinglog"

    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    consumer.set_last_timestamp(checkpoint)

    with requests_mock.Mocker() as mock_requests, patch("trendmicro_modules.trigger_email_sec.time.sleep"):
        mock_requests.get(url, [{"status_code": 200, "json": page} for page in pages])
        consumer.next_batch()

        # all the pages were requested, following the nextToken
        assert mock_requests.call_count == 3
        assert "token" not in mock_requests.request_history[0].qs
        assert mock_requests.request_history[1].qs["token"] == ["token/page2"]
        assert mock_requests.request_history[2].qs["token"] == ["token/page3"]

    pushed = [
        orjson.loads(event)["mailID"]
        for call in trigger.push_events_to_intakes.call_args_list
        for event in call.kwargs["events"]
    ]
    assert trigger.push_events_to_intakes.call_count == 3
    assert sorted(pushed) == ["mail-1", "mail-2", "mail-3", "mail-4", "mail-5", "mail-6"]

    # the checkpoint is the most recent genTime over all the pages
    assert consumer.get_last_timestamp() == max_gen_time
    # only the events at the checkpoint second are remembered
    assert sorted(event["mailID"] for event in consumer.get_recent_pushed_events()) == ["mail-2", "mail-5"]

    # the next run queries from the checkpoint, inclusive: the events of this second are returned again
    trigger.push_events_to_intakes.reset_mock()
    next_page = {"logs": [build_log("mail-5", max_gen_time), build_log("mail-2", max_gen_time)]}
    with requests_mock.Mocker() as mock_requests, patch("trendmicro_modules.trigger_email_sec.time.sleep"):
        mock_requests.get(url, status_code=200, json=next_page)
        consumer.next_batch()

        assert mock_requests.last_request.qs["start"] == [unixtime_to_iso8601(max_gen_time).lower()]

    # they are not pushed again
    assert trigger.push_events_to_intakes.call_count == 0
    assert consumer.get_last_timestamp() == max_gen_time

    # a new event in the same second is pushed, without duplicating the previous ones
    next_page["logs"].append(build_log("mail-7", max_gen_time))
    with requests_mock.Mocker() as mock_requests, patch("trendmicro_modules.trigger_email_sec.time.sleep"):
        mock_requests.get(url, status_code=200, json=next_page)
        consumer.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
    assert [orjson.loads(event)["mailID"] for event in trigger.push_events_to_intakes.call_args.kwargs["events"]] == [
        "mail-7"
    ]
    assert consumer.get_last_timestamp() == max_gen_time
    assert sorted(event["mailID"] for event in consumer.get_recent_pushed_events()) == ["mail-2", "mail-5", "mail-7"]


def test_checkpoint_not_moved_when_a_page_fails(trigger, paginated_responses):
    checkpoint, max_gen_time, pages = paginated_responses
    url = "https://api.tmes.trendmicro.eu/api/v1/log/mailtrackinglog"

    consumer = TrendMicroWorker(connector=trigger, log_type="accepted_traffic")
    consumer.set_last_timestamp(checkpoint)

    with requests_mock.Mocker() as mock_requests, patch("trendmicro_modules.trigger_email_sec.time.sleep"):
        mock_requests.get(
            url,
            [{"status_code": 200, "json": pages[0]}, {"status_code": 500, "text": "Internal Server Error"}],
        )
        consumer.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
    # the second page was not collected: the window must be collected again on the next run
    assert consumer.get_last_timestamp() == checkpoint
    assert consumer.get_recent_pushed_events() == []
