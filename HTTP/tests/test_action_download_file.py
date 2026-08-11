import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import pytest
import requests_mock
from pydantic import ValidationError

from http_module.action_download_file import DownloadFileAction

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
    assert "file_relative_path" in result

    # file_path is absolute
    abs_path = Path(result["file_path"])
    assert abs_path.is_absolute()
    assert abs_path.exists() is True

    # file_relative_path is relative and resolves correctly under data_path
    rel_path = Path(result["file_relative_path"])
    assert not rel_path.is_absolute()
    assert (symphony_storage / rel_path).exists() is True

    # Both point to the same file
    assert symphony_storage / rel_path == abs_path

    with abs_path.open("rb") as fp:
        assert fp.read() == FILE


def test_download_file_arguments_headers(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}
    result = action.run(dict(url=URL, headers={"foo": "bar"}))

    assert "file_path" in result
    assert "file_relative_path" in result
    assert "foo" in file_mock._adapter.last_request.headers
    assert file_mock._adapter.last_request.headers["foo"] == "bar"


def test_download_file_arguments_and_module_headers(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {"headers": {"foo": "bar", "other": "set"}}
    result = action.run(dict(url=URL, headers={"foo": "baz"}))

    assert "file_path" in result
    assert "file_relative_path" in result
    assert "foo" in file_mock._adapter.last_request.headers
    assert file_mock._adapter.last_request.headers["foo"] == "baz"  # The one used is the one from arguments
    assert file_mock._adapter.last_request.headers["other"] == "set"


def test_download_file_no_verify(symphony_storage, file_mock):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}
    result = action.run(dict(url=URL, verify_ssl=False))

    assert "file_path" in result
    assert "file_relative_path" in result
    assert file_mock._adapter.last_request.verify is False


@pytest.mark.parametrize(
    "url",
    ["C:\\Windows\\system32\\virus.exe", "google.com"],
)
def test_download_file_url_validation(symphony_storage, url):
    action = DownloadFileAction(data_path=symphony_storage)
    action.module.configuration = {}

    with pytest.raises(ValidationError):
        action.run(dict(url=url))


@pytest.mark.parametrize(
    "content_disposition, expected_filename",
    [
        ('attachment; filename="report.json"', "report.json"),
        ('attachment; filename=report.csv', "report.csv"),
    ],
)
def test_get_file_name_from_content_disposition(content_disposition, expected_filename):
    response = Mock()
    response.headers = {"Content-Disposition": content_disposition}

    assert DownloadFileAction._get_file_name(response) == expected_filename
