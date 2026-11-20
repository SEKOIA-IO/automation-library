"""Exercise streaming export, shared storage and failure cleanup without live credentials."""

import hashlib
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
import requests
import requests_mock
from s3path import S3Path

from microsoft_outlook_modules.action_export_message import ExportMessageAction


@pytest.fixture
def action(configured_action, tmp_path):
    action = configured_action(ExportMessageAction)
    action.__dict__["client"] = requests.Session()
    with patch.object(ExportMessageAction, "data_path", new_callable=PropertyMock, return_value=tmp_path):
        yield action


def test_eml_export_preserves_exact_mime_bytes_and_returns_reusable_file_path(action):
    raw = b"From: sender@example.org\r\nX-Custom: original\r\n\r\nBody\x00\xff\r\n"
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/$value", content=raw)
        result = action.run({"user": "u", "message_id": {"message_id": "m"}})
    assert result["outcome"] == "succeeded"
    assert (action.data_path / result["file_path"]).read_bytes() == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["size"] == len(raw) and result["content_type"] == "message/rfc822"
    assert result["file_name"] == result["file_path"]
    assert "base64_content" not in result


@pytest.mark.parametrize("advertised_size", [None, "1", str(2 * 1024 * 1024)])
def test_export_enforces_actual_size_even_if_content_length_is_missing_or_understated(action, advertised_size):
    with requests_mock.Mocker() as mock:
        headers = {} if advertised_size is None else {"Content-Length": advertised_size}
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/messages/m/$value",
            content=b"x" * (1024 * 1024 + 1),
            headers=headers,
        )
        result = action.run({"user": "u", "message_id": "m", "max_size_mb": 1})
    assert result["outcome"] == "failed" and "file_path" not in result
    assert not list(action.data_path.iterdir())


@pytest.mark.parametrize(
    "failure", [requests.Timeout, requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError]
)
def test_interrupted_export_cleans_partial_file_and_is_retryable(action, failure):
    response = MagicMock()
    response.headers = {}

    def chunks(**kwargs):
        yield b"partial bytes"
        raise failure("synthetic interruption")

    response.iter_content.side_effect = chunks
    response.__enter__.return_value = response
    graph = Mock()
    graph.request.return_value = response
    with patch("microsoft_outlook_modules.action_export_message.MailGraph", return_value=graph):
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "failed" and result["error_details"][0]["retryable"]
    assert not list(action.data_path.iterdir())


@pytest.mark.parametrize("status", [401, 403, 404, 429, 503])
def test_export_graph_errors_return_clean_results_without_files(action, status):
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/$value", status_code=status)
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "failed" and result["error_details"][0]["http_status"] == status
    assert not list(action.data_path.iterdir())


def test_empty_export_is_rejected_and_removed(action):
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/$value", content=b"")
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "failed" and not list(action.data_path.iterdir())


def test_s3_export_uses_binary_storage_without_local_path_operations(action):
    storage = MagicMock(spec=S3Path)
    storage.resolve.side_effect = NotImplementedError
    with (
        patch.object(ExportMessageAction, "data_path", new_callable=PropertyMock, return_value=storage),
        requests_mock.Mocker() as mock,
    ):
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/$value", content=b"MIME bytes")
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "succeeded"
    destination = storage.__truediv__.return_value
    destination.open.assert_called_once_with("wb")
    storage.resolve.assert_not_called()
    storage.mkdir.assert_not_called()


def test_failed_export_does_not_remove_preexisting_file(action):
    filename = "outlook-collision.eml"
    existing = action.data_path / filename
    existing.write_bytes(b"existing evidence")
    with (
        patch("microsoft_outlook_modules.action_export_message.uuid4", return_value="collision"),
        requests_mock.Mocker() as mock,
    ):
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/$value", content=b"new evidence")
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "failed"
    assert existing.read_bytes() == b"existing evidence"


def test_cleanup_failure_is_reported_without_claiming_a_completed_export(action):
    response = MagicMock()
    response.headers = {}
    response.__enter__.return_value = response
    response.iter_content.side_effect = requests.Timeout()
    graph = Mock()
    graph.request.return_value = response
    with (
        patch("microsoft_outlook_modules.action_export_message.MailGraph", return_value=graph),
        patch.object(type(action.data_path), "unlink", side_effect=OSError("storage unavailable")),
    ):
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "failed" and "file_path" not in result
    assert "incomplete file could not be removed" in result["error_details"][0]["message"]
