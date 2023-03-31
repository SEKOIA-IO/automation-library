from datetime import datetime, timedelta

import requests
from requests import HTTPError, Response


def get_upper_second(time: datetime) -> datetime:
    """
    Return the upper second from a datetime

    :param datetime time: The starting datetime
    :return: The upper second of the starting datetime
    :rtype: datetime
    """
    return (time + timedelta(seconds=1)).replace(microsecond=0)


def human_readable_api_error(any_exception: Exception) -> str:
    """
    Returns a string that explains the specified error.
    Supports:
    - ConnectionError
    - HTTPError
    - HTTPError with WithSecure Error Payload
    """

    if isinstance(any_exception, requests.exceptions.ConnectionError):
        connection_error: requests.exceptions.ConnectionError = any_exception
        return f"Failed to connect on WithSecure's API ('{connection_error.strerror}')"

    elif isinstance(any_exception, HTTPError) and isinstance(any_exception.response, Response):
        http_error: HTTPError = any_exception

        http_response: Response = http_error.response
        try:
            payload = http_response.json()
            if payload and "error_description" in payload:
                return f"WithSecure API returned '{payload['error_description']}' (status={http_response.status_code})"
            else:
                return f"WithSecure API rejected our request (status={http_response.status_code})"
        except ValueError as invalid_json_error:
            return f"WithSecure API rejected our request (status={http_response.status_code})"
    return str(any_exception)
