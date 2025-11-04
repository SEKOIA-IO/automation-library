import time
from unittest.mock import patch

import pytest

from utils.helpers import time_to_sleep, accurate_sleep


@pytest.mark.parametrize(
    "duration, expected_sleep",
    [
        (4000, 1333.3333),
        (300, 75.0),
        (100, 25.0),
        (20, 2.0),
        (10, 1.0),
        (5, 1.0),
        (1, 1.0),
        (0.5, 0.5),
        (-1, 0.0),
    ],
)
def test_time_to_sleep(duration, expected_sleep):
    sleep_time = time_to_sleep(duration)
    assert pytest.approx(sleep_time, 0.0001) == expected_sleep


def test_accurate_sleep():
    # List to record sleep calls
    sleep_calls = []

    # Get the initial time
    current_time = time.time()

    def mock_sleep(seconds):
        # Record each sleep call
        sleep_calls.append(seconds)

        # Simulate time passing
        nonlocal current_time
        current_time += seconds

    def mock_time():
        return current_time

    with patch("time.sleep", mock_sleep), patch("time.time", mock_time):
        accurate_sleep(10)

    # Assert that the function iterated 10 times
    assert len(sleep_calls) == 10

    # Assert that the total sleep time is approximately 10 seconds
    total_slept = sum(sleep_calls)
    assert pytest.approx(total_slept, 0.1) == 10

    # Assert that the total elapsed time is approximately 10 seconds
    assert pytest.approx(current_time - time.time(), 0.1) == 10
