from datetime import datetime
from unittest.mock import Mock, patch

from hornetsecurity_modules.timestepper import TimeStepper


def test_timestepper_creation_with_no_timedelta():
    trigger = Mock()
    frequency = 60
    timedelta = 0
    start_time = 0

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, timedelta, start_time)
        assert stepper.start == datetime(2023, 3, 22, 11, 55, 28)
        assert stepper.end == datetime(2023, 3, 22, 11, 56, 28)


def test_timestepper_creation_with_timedelta():
    trigger = Mock()
    frequency = 60
    timedelta = 5
    start_time = 0

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, timedelta, start_time)
        assert stepper.start == datetime(2023, 3, 22, 11, 50, 28)
        assert stepper.end == datetime(2023, 3, 22, 11, 51, 28)


def test_timestepper_creation_with_start_time():
    trigger = Mock()
    frequency = 60
    timedelta = 5
    start_time = 7

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, timedelta, start_time)
        assert stepper.start == datetime(2023, 3, 22, 4, 55, 28)
        assert stepper.end == datetime(2023, 3, 22, 4, 56, 28)


def test_timestepper_creation_from_time_cursor():
    trigger = Mock()
    frequency = 60
    timedelta = 0
    start = datetime(2023, 3, 22, 11, 56, 28)

    stepper = TimeStepper.create_from_time(trigger, start, frequency, timedelta)
    assert stepper.start == datetime(2023, 3, 22, 11, 56, 28)
    assert stepper.end == datetime(2023, 3, 22, 11, 57, 28)


@patch("hornetsecurity_modules.timestepper.time")
def test_timestepper_get_time_ranges_with_no_timedelta(mock_time):
    trigger = Mock()
    frequency = 60
    timedelta = 0
    start_time = 0

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.side_effect = [
            datetime(2023, 3, 22, 11, 56, 28),  # First call in TimeStepper.create!
            datetime(2023, 3, 22, 11, 56, 28),  # returned in TimeStepper.create
            datetime(2023, 3, 22, 11, 57, 50),  # compared in then 2nd iteration
            datetime(2023, 3, 22, 11, 58, 38),  # compared in the 3rd iteration
            datetime(2023, 3, 22, 11, 59, 16),  # compared in the 4th iteration
        ]
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, timedelta, start_time)
        gen = stepper.ranges()
        # Assert the 1st time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 55, 28),
            datetime(2023, 3, 22, 11, 56, 28),
        )
        # Assert the 2nd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 56, 28),
            datetime(2023, 3, 22, 11, 57, 28),
        )
        # Assert the 3rd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 57, 28),
            datetime(2023, 3, 22, 11, 58, 28),
        )
        # Ensure the stepper never waited before
        assert mock_time.sleep.called is False

        # Assert the 4th time range (end is 12 seconds in the future)
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 58, 28),
            datetime(2023, 3, 22, 11, 59, 28),
        )
        # Ensure the stepper waited 12 seconds
        mock_time.sleep.assert_called_with(12)


@patch("hornetsecurity_modules.timestepper.time")
def test_timestepper_get_time_ranges_with_timedelta(mock_time):
    trigger = Mock()
    frequency = 60
    time_lag = 5
    start_time = 0

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.side_effect = [
            datetime(2023, 3, 22, 11, 56, 28),  # first call in TimeStepper.create!
            datetime(2023, 3, 22, 11, 56, 28),  # compared in 1st iteration
            datetime(2023, 3, 22, 11, 57, 44),  # compared in 2nd iteration
            datetime(2023, 3, 22, 11, 58, 43),  # compared in 3rd iteration
            datetime(2023, 3, 22, 11, 59, 41),  # compared in 4th iteration
            datetime(2023, 3, 22, 12, 0, 37),  # compared in the 5th iteration
            datetime(2023, 3, 22, 12, 1, 33),  # compared in the 6th iteration
            datetime(2023, 3, 22, 12, 2, 29),  # compared in the 7th iteration
            datetime(2023, 3, 22, 11, 58, 22),  # compared in the 8th iteration
        ]
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, time_lag, start_time)
        gen = stepper.ranges()
        # assert the 1st time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 50, 28),
            datetime(2023, 3, 22, 11, 51, 28),
        )
        # assert the 2nd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 51, 28),
            datetime(2023, 3, 22, 11, 52, 28),
        )
        # assert the 3rd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 52, 28),
            datetime(2023, 3, 22, 11, 53, 28),
        )
        # assert the 4th time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 53, 28),
            datetime(2023, 3, 22, 11, 54, 28),
        )
        # assert the 5th time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 54, 28),
            datetime(2023, 3, 22, 11, 55, 28),
        )
        # assert the 6th time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 55, 28),
            datetime(2023, 3, 22, 11, 56, 28),
        )
        # assert the 7th time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 56, 28),
            datetime(2023, 3, 22, 11, 57, 28),
        )
        # Ensure the stepper never waited before
        assert mock_time.sleep.called is False
        # assert the 8th time range (end is 6 seconds in the future)
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 57, 28),
            datetime(2023, 3, 22, 11, 58, 28),
        )
        # Ensure the stepper waited 306 seconds.
        # Because original time lag is 5 minutes, but sleep accept seconds
        # So at the end it will wait 5 minutes + 6 seconds =306
        mock_time.sleep.assert_called_with(306)


@patch("hornetsecurity_modules.timestepper.time")
def test_timestepper_get_time_ranges_reach_max_wait_time(mock_time):
    trigger = Mock()
    frequency = 600
    timedelta = 0
    start_time = 0

    with patch("hornetsecurity_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.side_effect = [
            datetime(2023, 3, 22, 11, 50, 28),  # returned in TimeStepper.create
            datetime(2023, 3, 22, 11, 50, 28),  # compared in then 1st iteration
            datetime(2023, 3, 22, 12, 7, 50),  # compared in then 2nd iteration
            datetime(2023, 3, 22, 12, 13, 38),  # compared in the 3rd iteration
            datetime(2023, 3, 22, 12, 20, 29),  # compared in the 4th iteration
            datetime(2023, 3, 22, 12, 20, 27),  # compared in the 5th iteration
        ]
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        stepper = TimeStepper.create(trigger, frequency, timedelta, start_time)
        gen = stepper.ranges()
        # Assert the 1st time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 40, 28),
            datetime(2023, 3, 22, 11, 50, 28),
        )
        # Assert the 2nd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 11, 50, 28),
            datetime(2023, 3, 22, 12, 0, 28),
        )
        # Assert the 3rd time range
        assert next(gen) == (
            datetime(2023, 3, 22, 12, 0, 28),
            datetime(2023, 3, 22, 12, 10, 28),
        )
        # Assert the 4th time range
        assert next(gen) == (
            datetime(2023, 3, 22, 12, 10, 28),
            datetime(2023, 3, 22, 12, 20, 28),
        )
        # Ensure the stepper never waited before
        assert mock_time.sleep.called is False
        # Assert the 5th time range (end is 10 minutes in the future)
        assert next(gen) == (
            datetime(2023, 3, 22, 12, 20, 28),
            datetime(2023, 3, 22, 12, 30, 28),
        )
        # Ensure the stepper waited
        # Because we cannot perform request with data that is in the future,
        mock_time.sleep.assert_called_with(frequency + 1)
