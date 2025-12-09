import datetime
from unittest.mock import MagicMock, patch

import pytest

from ubika_modules.timestepper import TimeStepper


@pytest.fixture
def mock_trigger():
    trigger = MagicMock()
    trigger.log = MagicMock()
    trigger.configuration.intake_key = "test_intake_key"
    return trigger


@pytest.fixture
def fixed_time():
    return datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.UTC)


def test_timestepper_initialization(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 11, 0, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    assert stepper.trigger == mock_trigger
    assert stepper.start == start
    assert stepper.end == end
    assert stepper.frequency == frequency
    assert stepper.timedelta == timedelta


def test_ranges_yields_current_time_range_first(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 11, 0, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch("ubika_modules.timestepper.time"):
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.UTC)
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        generator = stepper.ranges()
        first_range = next(generator)

        assert first_range == (start, end)


def test_ranges_updates_start_and_end_after_iteration(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 10, 1, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch("ubika_modules.timestepper.time"):
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.UTC)
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        generator = stepper.ranges()
        next(generator)
        second_range = next(generator)

        assert second_range[0] == end
        assert second_range[1] > end


def test_ranges_sleeps_when_next_end_is_in_future(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 11, 58, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 11, 59, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch(
            "ubika_modules.timestepper.time") as mock_time:
        now = datetime.datetime(2024, 1, 15, 11, 59, 30, tzinfo=datetime.UTC)
        mock_datetime.datetime.now.return_value = now
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta
        mock_time.sleep = MagicMock()

        generator = stepper.ranges()
        next(generator)
        next(generator)

        assert mock_time.sleep.call_count == 1
        sleep_duration = mock_time.sleep.call_args[0][0]
        assert sleep_duration > 0


def test_ranges_does_not_sleep_when_next_end_is_in_past(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 10, 1, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch(
            "ubika_modules.timestepper.time") as mock_time:
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.UTC)
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta
        mock_time.sleep = MagicMock()

        generator = stepper.ranges()
        next(generator)
        next(generator)

        assert mock_time.sleep.call_count == 0


def test_create_with_default_parameters(mock_trigger, fixed_time):
    with patch("ubika_modules.timestepper.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = fixed_time
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        stepper = TimeStepper.create(mock_trigger)

        assert stepper.trigger == mock_trigger
        assert stepper.frequency == datetime.timedelta(seconds=60)
        assert stepper.timedelta == datetime.timedelta(minutes=1)
        assert stepper.end < fixed_time
        assert stepper.start < stepper.end


def test_create_with_start_time_zero(mock_trigger, fixed_time):
    with patch("ubika_modules.timestepper.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = fixed_time
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        stepper = TimeStepper.create(mock_trigger, start_time=0)

        expected_end = fixed_time - datetime.timedelta(minutes=1)
        assert stepper.end == expected_end


def test_create_with_custom_start_time(mock_trigger, fixed_time):
    with patch("ubika_modules.timestepper.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = fixed_time
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        stepper = TimeStepper.create(mock_trigger, start_time=2)

        expected_end = fixed_time - datetime.timedelta(hours=2)
        assert stepper.end == expected_end


def test_create_with_custom_frequency_and_timedelta(mock_trigger, fixed_time):
    with patch("ubika_modules.timestepper.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = fixed_time
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        stepper = TimeStepper.create(mock_trigger, frequency=120, timedelta=5)

        assert stepper.frequency == datetime.timedelta(seconds=120)
        assert stepper.timedelta == datetime.timedelta(minutes=5)


def test_create_from_time_with_default_parameters(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)

    stepper = TimeStepper.create_from_time(mock_trigger, start)

    assert stepper.trigger == mock_trigger
    assert stepper.start == start
    assert stepper.end == start + datetime.timedelta(seconds=60)
    assert stepper.frequency == datetime.timedelta(seconds=60)
    assert stepper.timedelta == datetime.timedelta(minutes=1)


def test_create_from_time_with_custom_parameters(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)

    stepper = TimeStepper.create_from_time(mock_trigger, start, frequency=300, timedelta=10)

    assert stepper.start == start
    assert stepper.end == start + datetime.timedelta(seconds=300)
    assert stepper.frequency == datetime.timedelta(seconds=300)
    assert stepper.timedelta == datetime.timedelta(minutes=10)


def test_ranges_logs_current_lag(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 10, 1, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch("ubika_modules.timestepper.time"):
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.UTC)
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta

        generator = stepper.ranges()
        next(generator)
        next(generator)

        assert mock_trigger.log.called
        log_calls = [call for call in mock_trigger.log.call_args_list if "Current lag" in str(call)]
        assert len(log_calls) > 0


def test_ranges_logs_waiting_message_when_sleeping(mock_trigger):
    start = datetime.datetime(2024, 1, 15, 11, 58, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2024, 1, 15, 11, 59, 0, tzinfo=datetime.UTC)
    frequency = datetime.timedelta(seconds=60)
    timedelta = datetime.timedelta(minutes=1)

    stepper = TimeStepper(mock_trigger, start, end, frequency, timedelta)

    with patch("ubika_modules.timestepper.datetime") as mock_datetime, patch(
            "ubika_modules.timestepper.time") as mock_time:
        now = datetime.datetime(2024, 1, 15, 11, 59, 30, tzinfo=datetime.UTC)
        mock_datetime.datetime.now.return_value = now
        mock_datetime.UTC = datetime.UTC
        mock_datetime.timedelta = datetime.timedelta
        mock_time.sleep = MagicMock()

        generator = stepper.ranges()
        next(generator)
        next(generator)

        log_calls = [call for call in mock_trigger.log.call_args_list if "Waiting" in str(call)]
        assert len(log_calls) > 0
