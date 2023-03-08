from datetime import datetime, timedelta


def get_upper_second(time: datetime) -> datetime:
    """
    Return the upper second from a datetime

    :param datetime time: The starting datetime
    :return: The upper second of the starting datetime
    :rtype: datetime
    """
    return (time + timedelta(seconds=1)).replace(microsecond=0)
