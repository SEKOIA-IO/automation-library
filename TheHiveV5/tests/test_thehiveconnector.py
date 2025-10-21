import pytest
import sys
import unittest.mock as mock
import requests_mock

from thehive.thehiveconnector import TheHiveConnector, key_exists
from thehive4py.errors import TheHiveError


def test_key_exists_with_valid_string():
    """Test key_exists function with a valid string key"""
    mapping = {"key1": "value1", "key2": "value2"}
    assert key_exists(mapping, "key1") is True
    assert key_exists(mapping, "key3") is False


def test_key_exists_with_invalid_type():
    """Test that key_exists raises TypeError when key is not a string"""
    mapping = {"key1": "value1"}
    with pytest.raises(TypeError) as exc_info:
        key_exists(mapping, 123)
    assert "key_to_check must be a string" in str(exc_info.value)


def test_connector_init_without_apikey():
    """Test that ValueError is raised when API key is empty"""
    with pytest.raises(ValueError) as exc_info:
        TheHiveConnector("http://localhost:9000", "", "TESTORG")
    assert "API key is required" in str(exc_info.value)


def test_connector_safe_call_with_thehive_error():
    """Test that _safe_call properly handles TheHiveError"""
    connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")

    def mock_function():
        raise TheHiveError(message="Test error", response=None)

    with pytest.raises(TheHiveError):
        connector._safe_call(mock_function)


def test_connector_safe_call_with_generic_exception():
    """Test that _safe_call properly handles generic exceptions"""
    connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")

    def mock_function():
        raise Exception("Generic error")

    with pytest.raises(Exception) as exc_info:
        connector._safe_call(mock_function)
    assert "Generic error" in str(exc_info.value)


def test_connector_alert_find():
    """Test alert_find method"""
    with requests_mock.Mocker() as mock_requests:
        url = "http://localhost:9000/api/v1/query"
        mock_requests.post(url=url, status_code=200, json=[{"_id": "alert1"}])

        connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")
        result = connector.alert_find(filters={"status": "New"})

        # Verify the request was made
        assert mock_requests.call_count == 1


def test_sekoia_to_thehive_with_non_dict_event():
    """Test sekoia_to_thehive skips non-dict events"""
    # Test with a list containing non-dict items
    # sekoia_to_thehive is called as a class method where data becomes self
    data = [
        {"source.ip": "192.168.1.1"},
        "not a dict",  # This should be skipped
        123,  # This should also be skipped
        {"destination.domain": "example.com"},
    ]

    observables = TheHiveConnector.sekoia_to_thehive(data, "AMBER", "AMBER", True)

    # Should only have 2 observables (skipping the non-dict items)
    assert len(observables) == 2
    assert any(obs["data"] == "192.168.1.1" for obs in observables)
    assert any(obs["data"] == "example.com" for obs in observables)


def test_comment_add_in_alert():
    """Test comment_add_in_alert method"""
    with requests_mock.Mocker() as mock_requests:
        alert_id = "~12345"
        comment_text = "Test comment"
        url = f"http://localhost:9000/api/v1/alert/{alert_id}/comment"
        mock_requests.post(url=url, status_code=201, json={"_id": "comment123", "message": comment_text})

        connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")
        result = connector.comment_add_in_alert(alert_id, comment_text)

        # Verify the request was made
        assert mock_requests.call_count == 1
