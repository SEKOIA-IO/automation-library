import json

import requests
from requests import HTTPError, Response


def human_readable_api_error(http_response: Response) -> str:
    try:
        payload = http_response.json()
        if payload and "message" in payload:
            more = ""
            if "details" in payload:
                more = " - " + json.dumps(payload["details"])

            return f"WithSecure API returned '{payload['message']}'{more} (status={http_response.status_code})"
        else:
            return f"WithSecure API rejected our request (status={http_response.status_code})"
    except ValueError as invalid_json_error:
        return f"WithSecure API rejected our request (status={http_response.status_code})"
    except Exception as any_exception:
        return f"WithSecure API rejected our request ({any_exception.__class__.__name__})"


def human_readable_api_exception(any_exception: Exception) -> str:
    """
    Returns a string that explains the specified error.
    Supports:
    - ConnectionError
    - HTTPError
    - HTTPError with WithSecure Error Payload
    """

    if isinstance(any_exception, requests.exceptions.ConnectionError):
        connection_error: requests.exceptions.ConnectionError = any_exception
        return f"Failed to connect on WithSecure's API ({connection_error.__class__.__name__})"

    elif isinstance(any_exception, HTTPError) and isinstance(any_exception.response, Response):
        http_error: HTTPError = any_exception

        http_response: Response = http_error.response

        return human_readable_api_error(http_response)

    return str(any_exception)
