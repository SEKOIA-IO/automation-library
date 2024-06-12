from datetime import datetime, timedelta


def split_date_range(start_date: datetime, end_date: datetime, delta: timedelta) -> list[tuple[datetime, datetime]]:
    """Splits a date range in shorter intervals with a set max duration

    This is a recursive method that, given a start and end date, will create a first tuple for the first 30
    minutes of the interval, then call itself to create the tuples of the subsequent 30 minutes intervals and
    append them at the end of the list of intervals.
    The last interval of the list may be of less than 30 minutes if the global interval duration is not a multiple
    of 30 minutes.

    Args:
        start_date (datetime): Current start date of the to-be-split interval
        end_date (datetime): End date of the to-be-split interval
        delta (timedelta): Max duration of the splits

    Returns:
        list[tuple[datetime, datetime]]: A list of subintervals covering of all the global interval
    """
    if end_date - start_date <= delta:
        return [(start_date, end_date)]
    else:
        return [(start_date, start_date + delta)] + split_date_range(start_date + delta, end_date, delta)
