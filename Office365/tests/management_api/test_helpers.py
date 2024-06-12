from datetime import datetime, timedelta

from office365.management_api.helpers import split_date_range


def test_split_date_range_should_return_one_range(connector):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(minutes=25)
    delta = timedelta(minutes=30)
    split = split_date_range(start_date, end_date, delta)

    assert split == [(start_date, end_date)]


def test_split_date_range_should_return_two_ranges(connector):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(minutes=45)
    delta = timedelta(minutes=30)
    split = split_date_range(start_date, end_date, delta)

    assert split == [(start_date, start_date + delta), (start_date + delta, end_date)]
