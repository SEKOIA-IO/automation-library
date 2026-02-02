"""Tests for the TimeStepper class."""

import datetime
from datetime import timezone
from unittest.mock import MagicMock

import pytest

from salesforce.timestepper import TimeStepper


@pytest.fixture
def mock_connector():
    """Create a mock connector for testing."""
    connector = MagicMock()
    connector.configuration.intake_key = "test_key"
    connector.log = MagicMock()
    return connector


def test_timestepper_create(mock_connector):
    """Test TimeStepper.create() factory method."""
    stepper = TimeStepper.create(
        mock_connector,
        frequency=300,
        timedelta=10,
        start_time=2,
    )

    assert stepper.connector == mock_connector
    assert stepper.frequency == datetime.timedelta(seconds=300)
    assert stepper.timedelta == datetime.timedelta(minutes=10)

    # End should be ~2 hours ago
    now = datetime.datetime.now(timezone.utc)
    expected_end = now - datetime.timedelta(hours=2)
    assert abs((stepper.end - expected_end).total_seconds()) < 5


def test_timestepper_create_start_time_zero(mock_connector):
    """Test TimeStepper.create() with start_time=0 (start from now)."""
    stepper = TimeStepper.create(
        mock_connector,
        frequency=600,
        timedelta=15,
        start_time=0,
    )

    # End should be now minus timedelta
    now = datetime.datetime.now(timezone.utc)
    expected_end = now - datetime.timedelta(minutes=15)
    assert abs((stepper.end - expected_end).total_seconds()) < 5


def test_timestepper_create_from_time(mock_connector):
    """Test TimeStepper.create_from_time() factory method."""
    start = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)

    stepper = TimeStepper.create_from_time(
        mock_connector,
        start,
        frequency=600,
        timedelta=15,
    )

    assert stepper.start == start
    assert stepper.end == start + datetime.timedelta(seconds=600)
    assert stepper.frequency == datetime.timedelta(seconds=600)
    assert stepper.timedelta == datetime.timedelta(minutes=15)


def test_timestepper_ranges_yields_correct_windows(mock_connector):
    """Test that ranges() yields correct time windows."""
    start = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=2)
    end = start + datetime.timedelta(minutes=10)

    stepper = TimeStepper(
        mock_connector,
        start,
        end,
        datetime.timedelta(minutes=10),
        datetime.timedelta(minutes=15),
    )

    ranges_gen = stepper.ranges()
    first_start, first_end = next(ranges_gen)

    assert first_start == start
    assert first_end == end


def test_timestepper_init(mock_connector):
    """Test TimeStepper initialization."""
    start = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)
    end = datetime.datetime.now(timezone.utc)
    frequency = datetime.timedelta(seconds=600)
    timedelta = datetime.timedelta(minutes=15)

    stepper = TimeStepper(mock_connector, start, end, frequency, timedelta)

    assert stepper.connector == mock_connector
    assert stepper.start == start
    assert stepper.end == end
    assert stepper.frequency == frequency
    assert stepper.timedelta == timedelta
