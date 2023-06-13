import hashlib
import zlib
from unittest.mock import Mock, call

import pytest

from imperva.fetch_logs import LogsDownloader


@pytest.fixture
def trigger(symphony_storage):
    trigger = LogsDownloader()
    trigger.testing = True
    trigger.module.configuration = {
        "api_id": "lorem",
        "api_key": "ipsum",
        "base_url": "https://imperva.test/api/",
    }
    trigger.configuration = {
        "frequency": 604800,
        "chunk_size": 20,
        "intake_key": "aaaaa",
    }
    trigger.log = Mock()

    trigger.initializing()

    trigger.file_downloader = Mock()
    trigger.logs_file_index = Mock()
    trigger.push_events_to_intakes = Mock()
    return trigger


def test_fetch_log(trigger):
    # first run : first try will not get content, then second call is successfully
    trigger.logs_file_index.indexed_logs = Mock(return_value=["42_42.log"])
    trigger.file_downloader.request_file_content = Mock(
        side_effect=["", b"lorem:ipsum|==|\n" + zlib.compress(b"a log")]
    )

    trigger.get_log_files()

    assert trigger.logs_file_index.indexed_logs.call_count == 1
    assert trigger.file_downloader.request_file_content.call_count == 2
    assert trigger.file_downloader.request_file_content.mock_calls == [
        call("https://imperva.test/api/42_42.log"),
        call("https://imperva.test/api/42_42.log"),
    ]
    assert trigger.push_events_to_intakes.called

    # reset mocks
    trigger.push_events_to_intakes.reset_mock()
    trigger.file_downloader.request_file_content.reset_mock()

    # second run
    trigger.file_downloader.request_file_content = Mock(return_value=b"lorem:ipsum|==|\n" + zlib.compress(b"a log"))

    trigger.get_log_files()

    trigger.file_downloader.request_file_content.assert_called_once_with("https://imperva.test/api/42_43.log")
    assert trigger.push_events_to_intakes.called

    # reset mocks
    trigger.push_events_to_intakes.reset_mock()
    trigger.file_downloader.request_file_content.reset_mock()

    # third run, will not achieve to handle 4 times (including one break that why two calls of get_log_file
    # before getting it
    trigger.file_downloader.request_file_content = Mock(
        side_effect=[
            "",
            "",
            "",
            b"lorem:ipsum|==|\nwrongdata",
            b"lorem:ipsum|==|\n" + zlib.compress(b"a log"),
        ]
    )
    trigger.get_log_files()
    trigger.get_log_files()
    assert trigger.push_events_to_intakes.called


def test_fetch_logs_10_retries_index_too_old(trigger):
    trigger.logs_file_index.indexed_logs = Mock(return_value=["42_44.log"])
    trigger.last_known_downloaded_file_id.last_id = "42_42.log"  # bypass first scan

    trigger.file_downloader.request_file_content = Mock(return_value="")

    for _ in range(11):
        trigger.get_log_files()

    assert trigger.last_known_downloaded_file_id.last_id == ""


def test_fetch_logs_10_retries_index_reset_retries(trigger):
    trigger.logs_file_index.indexed_logs = Mock(return_value=["42_42.log"])
    trigger.last_known_downloaded_file_id.last_id = "42_42.log"  # bypass first scan

    trigger.file_downloader.request_file_content = Mock(return_value="")

    for _ in range(11):  # < 10 retries, can continue forever
        trigger.get_log_files()


def test_fetch_logs_10_retries_index_skipping_file(trigger):
    trigger.logs_file_index.indexed_logs = Mock(return_value=["42_42.log", "42_44.log"])
    trigger.last_known_downloaded_file_id.last_id = "42_42.log"  # bypass first scan

    trigger.file_downloader.request_file_content = Mock(return_value="")

    for _ in range(11):
        trigger.get_log_files()

    assert trigger.last_known_downloaded_file_id.last_id == "42_43.log"


def test_decrypt_success():
    pass


def test_decrypt_file_key_missing_in_config():
    ld = LogsDownloader()
    ld.log = Mock()
    ld.configuration = {"keys": {"123456": {"private": "lorem ipsum dolor"}}}

    with pytest.raises(ValueError):
        ld.decrypt_file(b"key:a_sym_key\npublicKeyId:78910|==|\nsome logs", "filename")


def test_decrypt_file_key_exception_while_decrypting():
    ld = LogsDownloader()
    ld.log = Mock()
    ld.configuration = {"keys": {"123456": {"private": "lorem ipsum dolor"}}}

    with pytest.raises(IndexError):
        ld.decrypt_file(b"key:a_sym_key\npublicKeyId:123456|==|\nsome logs", "filename")


def test_validate_checksum():
    ld = LogsDownloader()

    md5 = hashlib.md5(b"foo").hexdigest()
    assert ld.validate_checksum(md5, b"foo") is True
    assert ld.validate_checksum(md5, b"bar") is False
