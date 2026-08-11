import json
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import pytest
import requests_mock
from pydantic import ValidationError
from requests.exceptions import ConnectionError, HTTPError
from tenacity import Retrying, wait_none

from http_module.action_request import RequestAction


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


def test_get_request(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            json={"foo": "bar"},
            status_code=200,
            reason="OK",
            headers={"h1": "foo", "h2": "bar", "Content-Type": "application/json"},
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io"})
        del result["elapsed"]
        json.dumps(result)
        assert result == {
            "encoding": "utf-8",
            "headers": {"h1": "foo", "h2": "bar", "Content-Type": "application/json"},
            "json": {"foo": "bar"},
            "reason": "OK",
            "status_code": 200,
            "text": '{"foo": "bar"}',
            "url": "https://api.sekoia.io/",
        }


def test_post_request(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api.sekoia.io",
            status_code=202,
            reason="Accepted",
            headers={"h1": "foo", "h2": "bar"},
        )

        result = action.run({"method": "post", "url": "https://api.sekoia.io", "data": {"att1": "val1"}})
        del result["elapsed"]
        json.dumps(result)
        assert result["status_code"] == 202
        assert mock.request_history[0].text == "att1=val1"


def test_post_request_json(symphony_storage):
    """Test POST request with JSON data."""
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    # JSON Object
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api.sekoia.io",
            json={"foo": "bar"},
            status_code=202,
            reason="Accepted",
            headers={"h1": "foo", "h2": "bar", "Content-Type": "application/json"},
        )

        result = action.run({"method": "post", "url": "https://api.sekoia.io", "json": {"foo": "bar"}})
        del result["elapsed"]
        json.dumps(result)
        assert result == {
            "encoding": "utf-8",
            "headers": {"h1": "foo", "h2": "bar", "Content-Type": "application/json"},
            "json": {"foo": "bar"},
            "reason": "Accepted",
            "status_code": 202,
            "text": '{"foo": "bar"}',
            "url": "https://api.sekoia.io/",
        }


def test_post_request_no_verify(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api.sekoia.io",
            status_code=202,
            reason="Accepted",
        )

        result = action.run({"method": "post", "url": "https://api.sekoia.io", "verify_ssl": False})
        assert result["status_code"] == 202
        assert mock.request_history[0].verify is False


def test_request_no_json_response(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    action.log_exception = Mock()

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            text="Hello",
            status_code=200,
            reason="OK",
            headers={"h1": "foo", "h2": "bar"},
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io"})
        del result["elapsed"]
        json.dumps(result)
        assert result == {
            "encoding": "utf-8",
            "headers": {"h1": "foo", "h2": "bar"},
            "json": None,
            "reason": "OK",
            "status_code": 200,
            "text": "Hello",
            "url": "https://api.sekoia.io/",
        }
        assert action.log_exception.call_count == 0


def test_request_invalid_json_response_body(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            text="not-a-json-payload",
            status_code=200,
            reason="OK",
            headers={"Content-Type": "application/json"},
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io"})
        assert result["json"] is None


def test_get_request_retry(symphony_storage, requests_mock):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    action._retry = lambda: Retrying(
        wait=wait_none(),
        reraise=True,
    )
    requests_mock.get(
        "https://api.sekoia.io",
        [
            {"exc": ConnectionError},
            {
                "json": {"foo": "bar"},
                "status_code": 500,
                "reason": "OK",
                "headers": {
                    "h1": "foo",
                    "h2": "bar",
                    "Content-Type": "application/json",
                },
            },
        ],
    )

    result = action.run(
        {"method": "get", "url": "https://api.sekoia.io", "raise_errors": False, "fail_on_http_error": False}
    )
    del result["elapsed"]
    json.dumps(result)
    assert result == {
        "encoding": "utf-8",
        "headers": {"h1": "foo", "h2": "bar", "Content-Type": "application/json"},
        "json": {"foo": "bar"},
        "reason": "OK",
        "status_code": 500,
        "text": '{"foo": "bar"}',
        "url": "https://api.sekoia.io/",
    }


@pytest.mark.parametrize(
    "params",
    [
        "param1=value1&param2=value2",
        {"param1": "value1", "param2": "value2"},
        '{"param1": "value1", "param2": "value2"}',
    ],
)
def test_request_with_params(symphony_storage, params):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            status_code=200,
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io", "params": params})
        del result["elapsed"]
        json.dumps(result)
        assert result["url"] == "https://api.sekoia.io/?param1=value1&param2=value2"


@pytest.mark.parametrize(
    "url",
    ["C:\\Windows\\system32\\virus.exe", "google.com"],
)
def test_url_validation(symphony_storage, url):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValidationError):
        action.run({"method": "get", "url": url})


@pytest.mark.parametrize(
    "method",
    ["trace", "options", "GET"],
)
def test_method_validation_against_schema_enum(symphony_storage, method):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValidationError):
        action.run({"method": method, "url": "https://api.sekoia.io"})


@pytest.mark.parametrize(
    "auth_type",
    ["ApiKey", "BearerToken", "basic"],
)
def test_auth_type_validation_against_schema_enum(symphony_storage, auth_type):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValidationError):
        action.run({"method": "get", "url": "https://api.sekoia.io", "auth_type": auth_type})


def test_auth_type_none_is_accepted(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            status_code=200,
            reason="OK",
            headers={"Content-Type": "application/json"},
            json={"ok": True},
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io", "auth_type": None})
        assert result["status_code"] == 200


def test_basic_auth(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            status_code=202,
            reason="Accepted",
            headers={"h1": "foo", "h2": "bar"},
        )

        result = action.run(
            {
                "method": "get",
                "url": "https://api.sekoia.io",
                "auth_type": "Basic",
                "auth_username": "user",
                "auth_password": "pass",
            }
        )
        assert result["status_code"] == 202
        assert mock.request_history[0].headers.get("Authorization", "").startswith("Basic ")


def test_basic_auth_miss_credentials(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValueError):
        action.run({"method": "get", "url": "https://api.sekoia.io", "auth_type": "Basic"})


def test_digest_auth(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            [
                # Simulate the Challenge and Response on the first request with no authentication
                {
                    "status_code": 401,
                    "reason": "Unauthorized",
                    "headers": {
                        "www-authenticate": 'digest realm="api.sekoia.io",qop="auth",nonce="abcdef",opaque="12345"'
                    },
                },
                {
                    "status_code": 202,
                    "reason": "Accepted",
                    "headers": {"h1": "foo", "h2": "bar"},
                },
            ],
        )

        result = action.run(
            {
                "method": "get",
                "url": "https://api.sekoia.io",
                "auth_type": "Digest",
                "auth_username": "user",
                "auth_password": "pass",
            }
        )
        assert result["status_code"] == 202
        assert mock.request_history[1].headers.get("Authorization", "").startswith("Digest ")


def test_digest_auth_miss_credentials(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValueError):
        action.run({"method": "get", "url": "https://api.sekoia.io", "auth_type": "Digest"})


def test_bearer_auth(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            status_code=202,
            reason="Accepted",
            headers={"h1": "foo", "h2": "bar"},
        )

        result = action.run(
            {"method": "get", "url": "https://api.sekoia.io", "auth_type": "Bearer", "auth_token": "my_token"}
        )
        assert result["status_code"] == 202
        assert mock.request_history[0].headers.get("Authorization", "").startswith("Bearer ")


def test_bearer_auth_miss_credentials(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValueError):
        action.run({"method": "get", "url": "https://api.sekoia.io", "auth_type": "Bearer"})


def test_request_fail_on_http_error_true(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            json={"error": "not_found"},
            status_code=404,
            reason="Not Found",
            headers={"Content-Type": "application/json"},
        )

        with pytest.raises(HTTPError):
            action.run({"method": "get", "url": "https://api.sekoia.io"})


def test_request_fail_on_http_error_false(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            json={"error": "not_found"},
            status_code=404,
            reason="Not Found",
            headers={"Content-Type": "application/json"},
        )

        result = action.run({"method": "get", "url": "https://api.sekoia.io", "fail_on_http_error": False})

        assert result["status_code"] == 404
        assert result["reason"] == "Not Found"
        assert result["json"] == {"error": "not_found"}


def test_request_redirection_response_is_successful(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    response = Mock()
    response.status_code = 302
    response.reason = "Found"
    response.text = ""
    response.ok = True

    action.handle_response(response=response, url="https://api.sekoia.io", fail_on_http_error=True)


def test_request_informational_response_is_successful(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    response = Mock()
    response.status_code = 101
    response.reason = "Switching Protocols"
    response.text = ""
    response.ok = True

    action.handle_response(response=response, url="https://api.sekoia.io", fail_on_http_error=True)


def test_request_server_error_raises_when_fail_on_http_error_true(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    response = Mock()
    response.status_code = 503
    response.reason = "Service Unavailable"
    response.text = "upstream timeout"
    response.ok = False
    response.raise_for_status.side_effect = HTTPError("503 Server Error")

    with pytest.raises(HTTPError):
        action.handle_response(response=response, url="https://api.sekoia.io", fail_on_http_error=True)


@pytest.mark.parametrize(
    "fail_on_http_error, expected_exception",
    [
        (True, HTTPError),
        (False, None),
    ],
)
def test_request_unexpected_status_handling(symphony_storage, fail_on_http_error, expected_exception):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}
    response = Mock()
    response.status_code = 700
    response.reason = "Out Of Range"
    response.text = ""
    response.ok = False
    response.raise_for_status.side_effect = HTTPError("700 Unexpected Error")

    if expected_exception:
        with pytest.raises(expected_exception):
            action.handle_response(
                response=response, url="https://api.sekoia.io", fail_on_http_error=fail_on_http_error
            )
    else:
        action.handle_response(response=response, url="https://api.sekoia.io", fail_on_http_error=fail_on_http_error)


def test_validate_url_accepts_valid_url(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    action.validate_url("https://api.sekoia.io")
