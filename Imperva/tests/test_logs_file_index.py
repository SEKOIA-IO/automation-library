from unittest.mock import Mock

import pytest

from imperva.fetch_logs import LogsFileIndex


def test_download_logs_index_success(config):
    file_downloader_mock = Mock()
    file_downloader_mock.request_file_content.return_value = b"42_42.log\n42_43.log\n42_44.log\n"

    lfi = LogsFileIndex(config, Mock(), file_downloader_mock)
    lfi.download()

    assert lfi.indexed_logs() == ["42_42.log", "42_43.log", "42_44.log"]


def test_download_logs_index_validation_error(config):
    file_downloader_mock = Mock()
    file_downloader_mock.request_file_content.return_value = b"wrong string"

    lfi = LogsFileIndex(config, Mock(), file_downloader_mock)
    with pytest.raises(ValueError):
        lfi.download()


def test_download_logs_index_no_index_file(config):
    file_downloader_mock = Mock()
    file_downloader_mock.request_file_content.return_value = ""

    lfi = LogsFileIndex(config, Mock(), file_downloader_mock)
    with pytest.raises(ValueError):
        lfi.download()


def test_validate_logs_index_file_format_false():
    assert not LogsFileIndex.validate_logs_index_file_format("loremipsumdolor")


def test_validate_log_file_format_false():
    assert not LogsFileIndex.validate_log_file_format("loremipsumdolor")
