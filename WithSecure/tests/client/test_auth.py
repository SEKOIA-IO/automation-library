from datetime import datetime, timedelta
from threading import Event
from unittest.mock import MagicMock, call

import pytest
import requests
import requests_mock
from requests import Request

import withsecure.client
from withsecure.client import OAuthAuthentication
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.client.exceptions import AuthenticationError


def fake_log_cb(message: str, level: str):
    print(message)
    return None


def test_get_access_token_trigger_authentication():
    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read connect.api.write",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        test_request = Request()
        oauth_authentication(test_request)
        assert test_request.headers == {"Authorization": "Bearer eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as"}


def test_api_client_check_validity_before_refresh():
    api_client = withsecure.client.ApiClient(
        client_id="test-client-id",
        secret="test-secret",
        scope="connect.api.read connect.api.write",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )

    api_client.auth.access_token_value = "fake-access-token"
    api_client.auth.access_token_valid_until = datetime.utcnow() + timedelta(minutes=10)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://my.fake.sekoia.io", status_code=200, json={})
        assert api_client.get("https://my.fake.sekoia.io").status_code == 200


def test_get_access_token_triggers_critical_log_on_auth_error(mocker):
    mocker.patch.object(withsecure.client.auth, "API_AUTH_RETRY_BACKOFF", 0)

    log_mock = MagicMock()
    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read connect.api.write",
        stop_event=Event(),
        log_cb=log_mock,
    )
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=401,
            json={"error_description": "Invalid credentials", "error": "invalid_client"},
        )
        test_request = Request()
        oauth_authentication(test_request)

        assert log_mock.mock_calls == [
            call("Authentication on WithSecure API failed with error: 'Invalid credentials'", "error"),
            call("Failed to authenticate on the WithSecure API", "critical"),
        ]


def test_authentication_success():
    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read connect.api.write",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )
    assert oauth_authentication.access_token_value == ""
    assert oauth_authentication.access_token_valid_until is None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        oauth_authentication.authenticate()

    assert oauth_authentication.access_token_value == "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as"
    assert oauth_authentication.access_token_valid_until > datetime.utcnow()


def test_authentication_failure_invalid_credentials():
    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )
    assert oauth_authentication.access_token_value == ""
    assert oauth_authentication.access_token_valid_until is None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=401,
            json={"error_description": "Invalid credentials", "error": "invalid_client"},
        )
        with pytest.raises(AuthenticationError):
            oauth_authentication.authenticate()

    assert oauth_authentication.access_token_value == ""
    assert oauth_authentication.access_token_valid_until is None


def test_authentication_failure_no_json(mocker):
    mocker.patch.object(withsecure.client.auth, "API_AUTH_MAX_ATTEMPT", 3)
    mocker.patch.object(withsecure.client.auth, "API_AUTH_RETRY_BACKOFF", 0)

    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(API_AUTHENTICATION_URL, status_code=500)
        with pytest.raises(AuthenticationError):
            oauth_authentication.authenticate()


def test_authentication_failure_invalid_json(mocker):
    mocker.patch.object(withsecure.client.auth, "API_AUTH_MAX_ATTEMPT", 3)
    mocker.patch.object(withsecure.client.auth, "API_AUTH_RETRY_BACKOFF", 0)

    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(API_AUTHENTICATION_URL, status_code=500, json={})
        with pytest.raises(AuthenticationError):
            oauth_authentication.authenticate()


def test_authentication_failure_connection_error(mocker):
    mocker.patch.object(withsecure.client.auth, "API_AUTH_MAX_ATTEMPT", 1)
    mocker.patch.object(withsecure.client.auth, "API_AUTH_RETRY_BACKOFF", 0)

    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(API_AUTHENTICATION_URL, exc=requests.exceptions.ConnectionError)
        with pytest.raises(AuthenticationError):
            oauth_authentication.authenticate()


def test_authentication_failure_unsupported_exception(mocker):
    mocker.patch.object(withsecure.client.auth, "API_AUTH_MAX_ATTEMPT", 1)
    mocker.patch.object(withsecure.client.auth, "API_AUTH_RETRY_BACKOFF", 0)

    oauth_authentication = OAuthAuthentication(
        client_id="test-client-id",
        secret="test-secret",
        grant_type="client_credentials",
        scope="connect.api.read",
        stop_event=Event(),
        log_cb=fake_log_cb,
    )

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(API_AUTHENTICATION_URL, exc=TimeoutError)
        with pytest.raises(AuthenticationError):
            oauth_authentication.authenticate()
