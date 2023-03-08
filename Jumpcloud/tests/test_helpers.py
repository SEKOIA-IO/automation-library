from datetime import datetime

from jumpcloud_modules.helpers import get_upper_second


def test_get_upper_second():
    starting_datetime = datetime(2022, 12, 11, 23, 45, 26, 208)
    expected_datetime = datetime(2022, 12, 11, 23, 45, 27)

    assert get_upper_second(starting_datetime) == expected_datetime
