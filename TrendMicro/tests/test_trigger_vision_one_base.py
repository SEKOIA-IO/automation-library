import threading
from datetime import datetime, timedelta, timezone

import pytest
from sekoia_automation.checkpoint import CheckpointDatetime

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_vision_one_base import (
    TrendMicroVisionOneBaseConfiguration,
    TrendMicroVisionOneBaseConnector,
)


class DummyVisionOneConnector(TrendMicroVisionOneBaseConnector):
    CONNECTOR_TITLE = "Dummy Vision One"
    CONNECTOR_METRICS_LABEL = "dummy_vision_one"

    def fetch_events(self):
        yield from self._events_to_fetch


def make_connector(symphony_storage, prepare_connector_mocks):
    connector = DummyVisionOneConnector(module=TrendMicroModule(), data_path=symphony_storage)
    connector = prepare_connector_mocks(connector)
    connector.configuration = TrendMicroVisionOneBaseConfiguration(
        base_url="https://api.xdr.trendmicro.com",
        api_key="01234556789abcdef",
        intake_key="intake_key",
        frequency=60,
    )
    connector._events_to_fetch = []
    return connector


@pytest.mark.parametrize(
    ("input_datetime", "expected_datetime"),
    [
        (
            datetime(2026, 1, 1, 12, 0, 0, 1000, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
        ),
    ],
)
def test_get_upper_second_rounds_to_next_second(input_datetime, expected_datetime):
    assert DummyVisionOneConnector.get_upper_second(input_datetime) == expected_datetime


def test_sanitize_from_date_returns_input_when_not_in_future(symphony_storage, prepare_connector_mocks):
    connector = make_connector(symphony_storage, prepare_connector_mocks)
    current = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert connector.sanitize_from_date(current) == current


def test_reset_cursor_offset_supports_subkey_and_lock(symphony_storage, prepare_connector_mocks):
    connector = make_connector(symphony_storage, prepare_connector_mocks)
    connector.cursor = CheckpointDatetime(
        path=connector._data_path,
        start_at=timedelta(minutes=1),
        ignore_older_than=None,
        lock=threading.Lock(),
        subkey="vision_one",
    )
    target = datetime.now(timezone.utc) - timedelta(minutes=2)

    connector.reset_cursor_offset(target)

    assert connector.cursor.offset == target


def test_next_batch_logs_no_events_when_generator_yields_empty_batch(
    symphony_storage,
    prepare_connector_mocks,
    mocked_vision_one_time,
):
    connector = make_connector(symphony_storage, prepare_connector_mocks)
    connector._events_to_fetch = [[]]

    mock_time = mocked_vision_one_time
    start_time = 1666711174.0
    end_time = start_time + 1
    mock_time.time.side_effect = [start_time, end_time]

    connector.next_batch()

    connector.log.assert_any_call(
        message="No events to forward connector=dummy_vision_one events_forwarded=0",
        level="debug",
    )
    mock_time.sleep.assert_called_once_with(59)


def test_base_fetch_events_raises_not_implemented(symphony_storage, prepare_connector_mocks):
    connector = make_connector(symphony_storage, prepare_connector_mocks)

    with pytest.raises(NotImplementedError):
        TrendMicroVisionOneBaseConnector.fetch_events(connector)


def test_reset_cursor_offset_supports_existing_subkey_cache_entry(symphony_storage, prepare_connector_mocks):
    connector = make_connector(symphony_storage, prepare_connector_mocks)
    connector.cursor = CheckpointDatetime(
        path=connector._data_path,
        start_at=timedelta(minutes=1),
        ignore_older_than=None,
        lock=threading.Lock(),
        subkey="vision_one",
    )
    first_target = datetime.now(timezone.utc) - timedelta(minutes=3)
    second_target = datetime.now(timezone.utc) - timedelta(minutes=2)

    connector.reset_cursor_offset(first_target)
    connector.reset_cursor_offset(second_target)

    assert connector.cursor.offset == second_target


def test_reset_cursor_offset_releases_lock_when_persistence_fails(symphony_storage, prepare_connector_mocks):
    class FailingContext:
        def __enter__(self):
            raise RuntimeError("persistence failed")

        def __exit__(self, exc_type, exc, tb):
            return False

    connector = make_connector(symphony_storage, prepare_connector_mocks)
    lock = threading.Lock()
    connector.cursor = CheckpointDatetime(
        path=connector._data_path,
        start_at=timedelta(minutes=1),
        ignore_older_than=None,
        lock=lock,
        subkey="vision_one",
    )
    connector.cursor._context = FailingContext()
    target = datetime.now(timezone.utc) - timedelta(minutes=2)

    with pytest.raises(RuntimeError, match="persistence failed"):
        connector.reset_cursor_offset(target)

    assert lock.acquire(blocking=False)
    lock.release()
