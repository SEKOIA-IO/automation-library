from unittest.mock import Mock, patch
import pytest
import requests

from hornetsecurity_modules.helpers import ApiError


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
