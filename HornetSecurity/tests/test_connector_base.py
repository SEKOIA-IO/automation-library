from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock

import pytest

from hornetsecurity_modules.connector_base import BaseConnector, BaseConnectorConfiguration


class DummyConnector(BaseConnector):
    ID_FIELD = "id"
    events: list[list[dict]] = []

    def set_events(self, events: list[list[dict]]) -> None:
        """
        Set the events to be returned by the connector.
        """
        self.events = events

    def _fetch_events(self, from_date: datetime, to_date: datetime) -> Generator[list[dict], None, None]:
        """
        Fetch events from the dummy connector.
        """
        yield from self.events
        yield []


@pytest.fixture
def connector_base(module, data_storage):
    connector = DummyConnector(module=module, data_path=data_storage)
    connector.configuration = BaseConnectorConfiguration(
        frequency=300,
        chunk_size=2,
        timedelta=0,
        ratelimit_per_second=20,
        intake_key="fake_intake_key",
    )
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.time_stepper.ranges = Mock(
        side_effect=[
            [
                (
                    datetime.now(timezone.utc) - timedelta(minutes=5),
                    datetime.now(timezone.utc),
                )
            ]
        ]
    )
    return connector


def test_connector_base_fetch_events_no_events(connector_base):
    """
    Test the fetch_events method of ConnectorBase when no events are returned.
    """
    connector_base.set_events([])

    with pytest.raises(StopIteration):
        next(connector_base.fetch_events())


def test_connector_base_fetch_events(connector_base):
    """
    Test the fetch_events method of ConnectorBase.
    """
    fetched_events = [
        {
            "id": "event1",
            "date": "2023-10-01T12:00:00Z",
            "direction": "Incoming",
            "subject": "Test Email 1",
        },
        {
            "id": "event2",
            "date": "2023-10-01T12:05:00Z",
            "direction": "Outgoing",
            "subject": "Test Email 2",
        },
        {
            "id": "event1",
            "date": "2023-10-01T12:05:00Z",
            "direction": "Incoming",
            "subject": "Test Email 2",
        },
    ]
    connector_base.set_events([fetched_events])

    events = next(connector_base.fetch_events())
    assert len(events) == 2
    assert events[0]["id"] == "event1"
    assert events[1]["id"] == "event2"


def test_connector_base_next_batch(connector_base):
    """
    Test the next_batch method of ConnectorBase.
    """
    fetched_events = [
        {
            "id": "event1",
            "date": "2023-10-01T12:00:00Z",
            "direction": "Incoming",
            "subject": "Test Email 1",
        },
        {
            "id": "event2",
            "date": "2023-10-01T12:05:00Z",
            "direction": "Outgoing",
            "subject": "Test Email 2",
        },
    ]
    connector_base.set_events([fetched_events])

    connector_base.next_batch()
    assert connector_base.push_events_to_intakes.call_count == 1
    calls = [call.kwargs["events"] for call in connector_base.push_events_to_intakes.call_args_list]
    assert len(calls[0]) == 2
