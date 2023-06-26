import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
import requests_mock

from http_module.download_file_action import DownloadFileAction

URL = "https://fake.url/my_file.json"
FILE = os.urandom(128)


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def file_mock():
    with requests_mock.Mocker() as mock:
        mock.get(URL, content=FILE)
        yield mock


def test_download_file(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}
    result = action.run(dict(url=URL))

    assert "file_path" in result
    path = symphony_storage / result["file_path"]
    assert path.exists() is True

    with path.open("rb") as fp:
        assert fp.read() == FILE


def test_download_file_arguments_headers(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}
    result = action.run(dict(url=URL, headers={"foo": "bar"}))

    assert "file_path" in result
    assert "foo" in file_mock._adapter.last_request.headers
    assert file_mock._adapter.last_request.headers["foo"] == "bar"


def test_download_file_arguments_and_module_headers(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {"headers": {"foo": "bar", "other": "set"}}
    result = action.run(dict(url=URL, headers={"foo": "baz"}))

    assert "file_path" in result
    assert "foo" in file_mock._adapter.last_request.headers
    assert file_mock._adapter.last_request.headers["foo"] == "baz"  # The one used is the one from arguments
    assert file_mock._adapter.last_request.headers["other"] == "set"


def test_download_file_no_verify(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}
    result = action.run(dict(url=URL, verify_ssl=False))

    assert "file_path" in result
    assert file_mock._adapter.last_request.verify is False
