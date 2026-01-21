import json
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import pytest
import requests_mock
from requests.exceptions import ConnectionError
from tenacity import Retrying, wait_none

from http_module.request_action import RequestAction


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

    result = action.run({"method": "get", "url": "https://api.sekoia.io", "raise_errors": False})
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


def test_get_request_error(symphony_storage, requests_mock):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    requests_mock.get("https://api.sekoia.io", status_code=500)

    action.run({"method": "get", "url": "https://api.sekoia.io"})
    assert action._error is not None


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


def test_basic_digest(symphony_storage):
    action = RequestAction(data_path=symphony_storage)
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.sekoia.io",
            [
                # Simulate the Chanllenge and Response on the first request with no authentication
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
