from unittest.mock import MagicMock

import pytest
from httpx import Response

from ubika_modules.connector_ubika_cloud_protector_next_gen_traffic_logs import (
    FetchEventsException,
    UbikaCloudProtectorNextGenTrafficLogsConnector,
    UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration,
)


class DummyContext:
    """
    In-memory stand-in for PersistentJSON.
    """

    def __init__(self):
        self.store = {}

    def __enter__(self):
        return self.store

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def connector(tmp_path):
    # Instantiate connector with a dummy module and tmp_path as data_path
    cfg = UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration(
        namespace="test-ns",
        refresh_token="rtoken",
        frequency=0,  # set to 0 to avoid real sleep
        chunk_size=2,
        start_time=1,  # backfill 1h on first run
    )
    # create the connector
    con = UbikaCloudProtectorNextGenTrafficLogsConnector(module=MagicMock(), data_path=str(tmp_path))
    # override its configuration and context
    con.configuration = cfg
    con.context = DummyContext()
    # replace real HTTP client with a simple mock
    con.client = MagicMock()
    # spy on publish
    con.publish_events_to_intake = MagicMock()
    return con


def make_response(items, token=None, status=200):
    """
    Helper to build a fake httpx.Response returning a spec with items and optional nextPageToken.
    """
    payload = {"spec": {"items": items}}
    if token is not None:
        payload["spec"]["nextPageToken"] = token
    return Response(status, json=payload)


def test_fetch_pages_paginates_until_empty(connector):
    # Prepare two pages: first has 2 items + token, second has empty items
    page1 = [{"timestamp": "1000"}, {"timestamp": "1100"}]
    page2 = []
    connector.client.get.side_effect = [
        make_response(page1, token="abc"),
        make_response(page2, token=None),
    ]

    # Collect pages
    pages = list(connector._fetch_pages(start_timestamp=500))
    assert pages == [page1]

    # Ensure client.get was called twice
    assert connector.client.get.call_count == 2


def test_fetch_pages_raises_on_http_error(connector):
    # Prepare a non-200 response in first call
    bad_resp = make_response([], token=None, status=500)
    connector.client.get.return_value = bad_resp

    # _handle_response_error will raise FetchEventsException
    with pytest.raises(FetchEventsException):
        # first call happens in _fetch_pages
        next(connector._fetch_pages(start_timestamp=0))


def test_fetch_pages_raises_on_auth_error(connector):
    # Make client.get throw AuthorizationError on first call
    from ubika_modules.client.auth import AuthorizationError

    connector.client.get.side_effect = AuthorizationError("auth_failed")

    with pytest.raises(AuthorizationError):
        next(connector._fetch_pages(start_timestamp=0))


def test_run_backfill_and_checkpoint(connector):
    """
    Validate that run():
     - uses backfill hours on first run
     - publishes exactly the events from _fetch_pages
     - stores the highest timestamp as checkpoint
    """
    # Simulate a single page with two events
    evts = [{"timestamp": "1000"}, {"timestamp": "1500"}]
    connector._fetch_pages = MagicMock(return_value=[evts])

    # Let the loop run exactly one iteration: first False => run once, then True => break
    connector._stop_event.is_set = MagicMock(side_effect=[False, True])

    # Run the connector
    connector.run()

    # publish_events_to_intake should have been called once
    connector.publish_events_to_intake.assert_called_once()
    # extract the argument: a list of JSON-strings
    published = connector.publish_events_to_intake.call_args[1]["events"]
    # We published exactly 2 events
    assert len(published) == 2
    # Check that the JSON matches the original dicts
    assert all(isinstance(s, str) for s in published)
    assert '"timestamp":"1000"' in published[0]

    # The dummy context should hold the maximum timestamp seen = 1500
    assert connector.context.store["most_recent_timestamp_seen"] == 1500


def test_run_respects_existing_checkpoint(connector):
    """
    If a checkpoint already exists, backfill is skipped and start_ts = checkpoint.
    """
    # Preload context with an existing checkpoint 2000 ms
    connector.context.store["most_recent_timestamp_seen"] = 2000

    # Override _fetch_pages to return a single page with lower timestamps
    # (simulate that no new events arrived)
    connector._fetch_pages = MagicMock(return_value=[[{"timestamp": "1800"}]])

    connector._stop_event.is_set = MagicMock(side_effect=[False, True])
    connector.run()

    # Since 1800 < 2000, the stored checkpoint remains 2000
    assert connector.context.store["most_recent_timestamp_seen"] == 2000
    # publish called once with the single event
    connector.publish_events_to_intake.assert_called_once()


def test_run_handles_empty_no_publish(connector):
    """
    If _fetch_pages yields an empty list or no pages, publish is never called.
    """
    connector._fetch_pages = MagicMock(return_value=[])
    connector._stop_event.is_set = MagicMock(side_effect=[False, True])

    connector.run()

    connector.publish_events_to_intake.assert_not_called()
    # checkpoint should still be set to first backfill point
    ts = connector.context.store["most_recent_timestamp_seen"]
    assert isinstance(ts, int) and ts > 0
