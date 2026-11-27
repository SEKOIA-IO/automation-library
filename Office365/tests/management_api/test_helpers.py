from datetime import UTC, datetime, timedelta

import pytest

from office365.management_api.helpers import split_date_range

END_DATE = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
DELTA = timedelta(minutes=30)


@pytest.mark.parametrize(
    "start_date,expected_ranges",
    [
        pytest.param(END_DATE, [(END_DATE, END_DATE)], id="zero_length_range"),
        pytest.param(END_DATE - timedelta(minutes=25), [(END_DATE - timedelta(minutes=25), END_DATE)], id="one_range"),
        pytest.param(END_DATE - DELTA, [(END_DATE - DELTA, END_DATE)], id="exactly_one_delta"),
        pytest.param(
            END_DATE - timedelta(minutes=45),
            [
                (END_DATE - timedelta(minutes=45), END_DATE - timedelta(minutes=15)),
                (END_DATE - timedelta(minutes=15), END_DATE),
            ],
            id="two_ranges",
        ),
    ],
)
def test_split_date_range(start_date, expected_ranges):
    assert list(split_date_range(start_date, END_DATE, DELTA)) == expected_ranges


def test_split_date_range_should_return_ranges_lesser_or_equal_to_delta():
    start_date = END_DATE - timedelta(hours=26)

    ranges = list(split_date_range(start_date, END_DATE, DELTA))

    assert len(ranges) == 52
    assert ranges[0][0] == start_date
    assert ranges[-1][1] == END_DATE
    assert all(end - start <= DELTA for start, end in ranges)
