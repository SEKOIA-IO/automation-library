from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from hornetsecurity_modules.helpers import ApiError, utc_zulu_format


def test_api_error_from_response():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.return_value = {
        "error_id": "123",
        "error_data": "Some data",
        "error_message": "An error occurred",
    }

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "123"
    assert api_error.data == "Some data"
    assert api_error.message == "An error occurred"


def test_api_error_from_response_without_details():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.return_value = {}

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "N/A"
    assert api_error.data == "N/A"
    assert api_error.message == "Unknown error"


def test_api_error_from_response_with_invalid_details():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.side_effect = ValueError("invalid json")

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "N/A"
    assert api_error.data == "N/A"
    assert api_error.message == "Unknown error"


@pytest.mark.parametrize(
    "dt, expected",
    [
        (datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc), "2023-10-01T12:00:00Z"),
        (datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5))), "2023-10-01T17:00:00Z"),
    ],
)
def test_utc_zulu_format(dt, expected):
    formatted_date = utc_zulu_format(dt)
    assert formatted_date == expected
