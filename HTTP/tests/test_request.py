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
