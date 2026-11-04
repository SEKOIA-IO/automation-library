from datetime import UTC, datetime, timedelta

import pytest
import requests_mock
from requests.exceptions import HTTPError

from secuserve_modules.connector_esecuremail_events import MAX_TIME_RANGE, PUBLICATION_DELAY

from .conftest import API_URL, set_cursor

EVENT_DELIVERED = (
    '{"message_id":"23e0.64facee0.bc601.0","client_ip":"161.38.205.161","stamp_queued":1727254241,'
    '"sender":"newsletter@example.com","subject":"Hello","message_size":87879,'
    '"recipient":"john.doe@example.net","stamp_filter":1727254241,"verdict":"valid","action":"pass",'
    '"delivery_status":"sent","antispam_score":1.2}'
)
EVENT_BLOCKED = (
    '{"message_id":"1a2b.64facee0.bc601.0","client_ip":"203.0.113.7","stamp_queued":1727254300,'
    '"sender":"spammer@evil.example","subject":"Your invoice","message_size":4211,'
    '"recipient":"accounting@example.net","stamp_filter":1727254302,"verdict":"spam","action":"blocked",'
    '"antispam_score":18.4}'
)


def test_fetch_events_returns_one_event_per_line(connector):
    start = datetime(2024, 9, 25, 8, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)

    with requests_mock.Mocker() as mock:
        mock.get(
            API_URL,
            text=f"{EVENT_DELIVERED}\n{EVENT_BLOCKED}\n",
            headers={"X-Query-End-Time": "1727254500"},
        )
        events, served_end = connector.fetch_events(start, end)

        assert events == [EVENT_DELIVERED, EVENT_BLOCKED]
        assert served_end == datetime.fromtimestamp(1727254500, tz=UTC)

        # the connector drives the period itself and asks for the flat format
        query = mock.last_request.qs
        assert query["format"] == ["flat"]
        assert query["interval"] == ["2024-09-25t08:00:00z/2024-09-25t08:05:00z"]
        assert mock.last_request.headers["Authorization"] == "Bearer an-api-key"


def test_fetch_events_without_event(connector):
    start = datetime(2024, 9, 25, 8, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)

    with requests_mock.Mocker() as mock:
        mock.get(API_URL, text="", headers={"X-Query-End-Time": "1727254500"})
        events, _ = connector.fetch_events(start, end)

        assert events == []


def test_fetch_events_falls_back_on_the_requested_bound(connector):
    """Without a usable X-Query-End-Time header, the requested bound is kept."""
    start = datetime(2024, 9, 25, 8, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)

    with requests_mock.Mocker() as mock:
        mock.get(API_URL, text=f"{EVENT_DELIVERED}\n")
        _, served_end = connector.fetch_events(start, end)
        assert served_end == end

        mock.get(API_URL, text="", headers={"X-Query-End-Time": "not-a-timestamp"})
        _, served_end = connector.fetch_events(start, end)
        assert served_end == end


def test_fetch_events_rejects_an_invalid_api_key(connector):
    start = datetime(2024, 9, 25, 8, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)

    with requests_mock.Mocker() as mock:
        mock.get(API_URL, status_code=401, json={"error": "Access token is missing or invalid"})

        with pytest.raises(HTTPError, match="Authentication failed"):
            connector.fetch_events(start, end)


def test_next_time_range_is_capped_to_one_hour(connector):
    set_cursor(connector, datetime.now(UTC) - timedelta(days=1))
    start, end = connector.next_time_range()

    assert end - start == MAX_TIME_RANGE


def test_next_time_range_stops_before_the_publication_delay(connector):
    set_cursor(connector, datetime.now(UTC) - timedelta(seconds=30))

    assert connector.next_time_range() is None


def test_next_time_range_leaves_the_publication_delay_out(connector):
    set_cursor(connector, datetime.now(UTC) - timedelta(minutes=10))
    _, end = connector.next_time_range()

    assert end <= datetime.now(UTC) - PUBLICATION_DELAY


def test_next_batch_pushes_events_and_moves_the_cursor_forward(connector):
    set_cursor(connector, datetime.now(UTC) - timedelta(minutes=10))
    served_end = int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())

    with requests_mock.Mocker() as mock:
        mock.get(
            API_URL,
            text=f"{EVENT_DELIVERED}\n{EVENT_BLOCKED}\n",
            headers={"X-Query-End-Time": str(served_end)},
        )
        catching_up = connector.next_batch()

    assert catching_up is False
    connector.push_events_to_intakes.assert_called_once_with(events=[EVENT_DELIVERED, EVENT_BLOCKED])
    # the bounds of the API are inclusive: the next window starts one second later
    assert connector.cursor.offset == datetime.fromtimestamp(served_end + 1, tz=UTC)


def test_next_batch_reports_it_is_still_catching_up(connector):
    start = datetime.now(UTC) - timedelta(days=1)
    set_cursor(connector, start)
    served_end = int((start + MAX_TIME_RANGE).timestamp())

    with requests_mock.Mocker() as mock:
        mock.get(API_URL, text="", headers={"X-Query-End-Time": str(served_end)})
        assert connector.next_batch() is True


def test_next_batch_without_a_new_period(connector):
    set_cursor(connector, datetime.now(UTC) - timedelta(seconds=30))

    assert connector.next_batch() is False
    connector.push_events_to_intakes.assert_not_called()


def test_events_are_pushed_by_chunks(connector):
    connector.push_events(["a", "b", "c"])

    assert connector.push_events_to_intakes.call_count == 2
    assert connector.push_events_to_intakes.call_args_list[0].kwargs == {"events": ["a", "b"]}
    assert connector.push_events_to_intakes.call_args_list[1].kwargs == {"events": ["c"]}
