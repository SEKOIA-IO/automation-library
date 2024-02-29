from datetime import datetime, timedelta

import pytest
import pytz

from connectors.broadcom_cloud_swg_connector import DatetimeRange


@pytest.fixture
def sample_datetime_range():
    start_date = datetime(2023, 1, 1, tzinfo=pytz.utc)
    end_date = datetime(2023, 1, 5, tzinfo=pytz.utc)

    return DatetimeRange(start_date=start_date, end_date=end_date)


@pytest.mark.asyncio
async def test_properties():
    start_date = None
    end_date = None
    date_range_1 = DatetimeRange(start_date, end_date)
    assert date_range_1.utc_end_date is None
    assert date_range_1.utc_start_date is None

    start_date_utc = datetime.now(pytz.utc)
    end_date_utc = datetime.now(pytz.utc) - timedelta(hours=123)
    date_range_2 = DatetimeRange(start_date_utc, end_date_utc)
    assert date_range_2.utc_end_date.isoformat() == end_date_utc.isoformat()
    assert date_range_2.utc_start_date.isoformat() == start_date_utc.isoformat()

    custom_timezone_offset = 180  # UTC+3
    custom_timezone = pytz.FixedOffset(custom_timezone_offset)

    start_date_non_utc = datetime.now(custom_timezone)
    end_date_non_utc = datetime.now(custom_timezone) - timedelta(hours=123)
    date_range_3 = DatetimeRange(start_date_non_utc, end_date_non_utc)
    assert date_range_3.utc_end_date.isoformat() != end_date_non_utc.isoformat()
    assert date_range_3.utc_start_date.isoformat() != start_date_non_utc.isoformat()


@pytest.mark.asyncio
async def test_contains(sample_datetime_range):
    # Test for value within the range
    assert sample_datetime_range.contains(datetime(2023, 1, 3, tzinfo=pytz.utc)) is True

    # Test for value just outside the end of the range
    assert sample_datetime_range.contains(datetime(2023, 1, 5, tzinfo=pytz.utc) + timedelta(seconds=1)) is False

    # Test for value just outside the start of the range
    assert sample_datetime_range.contains(datetime(2023, 1, 1, tzinfo=pytz.utc) - timedelta(seconds=1)) is False


@pytest.mark.asyncio
async def test_update_with(sample_datetime_range):
    new_date = datetime(2023, 1, 10, tzinfo=pytz.utc)
    updated_range = sample_datetime_range.update_with(new_date)

    assert updated_range.start_date == datetime(2023, 1, 1, 0, 0, 0, 1, tzinfo=pytz.utc)
    assert updated_range.end_date == datetime(2023, 1, 9, 23, 59, 59, 999999, tzinfo=pytz.utc)


@pytest.mark.asyncio
async def test_duplicate(sample_datetime_range):
    duplicate_range = sample_datetime_range.duplicate()
    assert duplicate_range.start_date == sample_datetime_range.start_date
    assert duplicate_range.end_date == sample_datetime_range.end_date


@pytest.mark.asyncio
async def test_to_dict(sample_datetime_range):
    expected_result = {"start_date": "2023-01-01T00:00:00+00:00", "end_date": "2023-01-05T00:00:00+00:00"}
    assert sample_datetime_range.to_dict() == expected_result


@pytest.mark.asyncio
async def test_from_dict():
    input_dict = {"start_date": "2023-01-01T00:00:00+00:00", "end_date": "2023-01-05T00:00:00+00:00"}
    expected_start_date = datetime(2023, 1, 1, tzinfo=pytz.utc)
    expected_end_date = datetime(2023, 1, 5, tzinfo=pytz.utc)
    result = DatetimeRange.from_dict(input_dict)
    assert result.start_date == expected_start_date
    assert result.end_date == expected_end_date
