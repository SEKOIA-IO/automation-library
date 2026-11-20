"""Regression coverage for evidence retrieval, Graph semantics and SDK execution."""

import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch

import jsonschema
import pytest
import requests
import requests_mock
from requests.exceptions import InvalidHeader

from microsoft_outlook_modules.action_download_attachments import DownloadAttachmentsAction
from microsoft_outlook_modules.action_extract_email import ExtractEmailAction
from microsoft_outlook_modules.action_list_messages import ListMessagesAction
from microsoft_outlook_modules.action_move_message import MoveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.attachments import collect_attachments
from microsoft_outlook_modules.client import ApiClient
from microsoft_outlook_modules.client.retry import Retry
from microsoft_outlook_modules.graph import MAX_ATTACHMENT_SIZE, MailGraph
from microsoft_outlook_modules.message_ids import graph_message_id


@pytest.mark.parametrize("value", ["Mixed+Case@example.com", "<Mixed+Case@example.com>", " <Mixed+Case@example.com> "])
def test_message_id_keeps_case_and_normalizes_wrappers(value):
    assert graph_message_id(value) == "<Mixed+Case@example.com>"


@pytest.mark.parametrize("value", ["", " ", "<abc", "abc>", "<<abc>>", "a\nb", "<>"])
def test_invalid_message_id_is_rejected(value):
    with pytest.raises(ValueError):
        graph_message_id(value)


@pytest.mark.parametrize("value", ["Mixed+Case@example.com", "<Mixed+Case@example.com>"])
def test_official_search_sends_bracketed_identifier(configured_action, value):
    action = configured_action(SearchMessagesAction)
    action.__dict__["client"] = requests.Session()
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.microsoft.com/v1.0/users/1111/messages", json={"value": []})
        result = action.run({"user": "1111", "email_message_id": value})
        assert mock.last_request.qs["$filter"] == ["internetmessageid eq '<mixed+case@example.com>'"]
        # requests_mock.qs lowercases by default; inspect the actual URL for original case.
        assert "Mixed%2BCase" in mock.last_request.url
        assert result["query_value"] == "<Mixed+Case@example.com>"


@pytest.mark.parametrize("parent,status", [("junk-id", "verified"), ("inbox-id", "mismatch")])
def test_move_uses_returned_id_for_independent_verification(configured_action, parent, status):
    action = configured_action(MoveMessageAction)
    action.__dict__["client"] = requests.Session()
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/junkemail",
            json={"id": "junk-id", "displayName": "Junk Email"},
        )
        mock.post("https://graph.microsoft.com/v1.0/users/u/messages/old/move", json={"id": "new"})
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/new", json={"id": "new", "parentFolderId": parent})
        result = action.run({"user": "u", "message_id": {"message_id": "old"}, "destination_folder": "junkemail"})
        assert mock.request_history[1].json() == {"destinationId": "junk-id"}
        assert result["execution_status"] == "succeeded"
        assert result["message_id"] == "new"
        assert result["verification_status"] == status


@pytest.mark.parametrize("failure_stage", ["move", "verification", "missing_id"])
def test_move_never_confuses_execution_and_verification_failures(configured_action, failure_stage):
    action = configured_action(MoveMessageAction)
    action.__dict__["client"] = requests.Session()
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/junkemail",
            json={"id": "junk-id", "displayName": "Junk Email"},
        )
        if failure_stage == "move":
            mock.post("https://graph.microsoft.com/v1.0/users/u/messages/old/move", exc=requests.Timeout)
        else:
            mock.post(
                "https://graph.microsoft.com/v1.0/users/u/messages/old/move",
                json={} if failure_stage == "missing_id" else {"id": "new"},
            )
            mock.get("https://graph.microsoft.com/v1.0/users/u/messages/new", exc=requests.Timeout)
        result = action.run({"user": "u", "message_id": "old", "destination_folder": "junkemail"})
        assert result["execution_status"] == ("failed_or_unknown" if failure_stage == "move" else "succeeded")
        assert result["verification_status"] == ("not_performed" if failure_stage == "move" else "unknown")
        assert len(result["errors"]) == 1
        assert sum(request.method == "POST" for request in mock.request_history) == 1


def test_folder_search_escapes_odata_and_reports_partial_page(configured_action):
    action = configured_action(ListMessagesAction)
    action.__dict__["client"] = requests.Session()
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/inbox", json={"id": "folder", "displayName": "Inbox"}
        )
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/folder/messages",
            json={"value": [{"id": "one", "parentFolderId": "folder"}], "@odata.nextLink": "next"},
        )
        result = action.run(
            {
                "user": "u",
                "subject_filter": "O'Brien",
                "email_message_id": "Mixed@example.com",
                "max_messages_to_return": 1,
            }
        )
        query = mock.last_request.qs["$filter"][0]
        assert query.startswith("receiveddatetime ge ")
        assert "o''brien" in query
        assert "internetmessageid eq '<mixed@example.com>'" in query
        assert result["has_more"] is True
        assert result["messages"][0]["parent_folder_id"] == "folder"
        assert result["message_ids"] == ["one"]
        assert len(mock.request_history) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/v1.0/users/u/messages",
        "http://graph.microsoft.com/v1.0/users",
        "https://graph.microsoft.com.evil.example/v1.0/users",
        "https://graph.microsoft.com/beta/users",
    ],
)
def test_nextlink_cannot_redirect_authenticated_requests(url):
    graph = MailGraph(Mock())
    with pytest.raises(ValueError):
        graph.page(url)
    graph.session.request.assert_not_called()


def test_attachments_enforce_downloaded_size_even_without_metadata():
    graph = MailGraph(requests.Session())
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/messages/m/attachments/a/$value",
            content=b"x" * (MAX_ATTACHMENT_SIZE + 1),
        )
        with pytest.raises(ValueError, match="limit"):
            graph.attachment_bytes("u", "m", {"id": "a"})


def test_attachments_enforce_inline_size_and_strict_base64():
    graph = MailGraph(Mock())
    with pytest.raises(ValueError, match="limit"):
        graph.attachment_bytes("u", "m", {"size": MAX_ATTACHMENT_SIZE + 1})
    with pytest.raises(ValueError):
        graph.attachment_bytes("u", "m", {"contentBytes": "!not-base64!"})
    graph.session.request.assert_not_called()


def test_attached_message_raw_mime_has_hash_and_source_reference(sample_eml_b64):
    graph = MailGraph(requests.Session())
    raw = base64.b64decode(sample_eml_b64)
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/messages/m/attachments",
            json={
                "value": [
                    {"id": "a", "name": "", "contentType": None, "@odata.type": "#microsoft.graph.itemAttachment"}
                ]
            },
        )
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/m/attachments/a/$value", content=raw)
        attachments, parsed, errors = collect_attachments(graph, "u", "m", embedded_only=True)
    assert errors == []
    assert parsed[0]["message_id"] == "<original@evil.com>"
    assert parsed[0]["source_sha256"] == attachments[0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert parsed[0]["source_attachment_id"] == "a"


def test_one_bad_attachment_does_not_hide_other_evidence(sample_eml_b64):
    graph = Mock(spec=MailGraph)
    graph.attachments.return_value = [{"id": "a", "name": "bad.eml"}, {"id": "b", "name": "good.eml"}]
    graph.attachment_bytes.side_effect = [b"not an email", base64.b64decode(sample_eml_b64)]
    attachments, parsed, errors = collect_attachments(graph, "u", "m")
    assert len(attachments) == 2
    assert len(parsed) == 1
    assert errors[0]["attachment_id"] == "a"


def test_binary_download_is_not_misreported_as_email_parse_failure(configured_action):
    action = configured_action(DownloadAttachmentsAction)
    action.__dict__["client"] = requests.Session()
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/messages/m/attachments",
            json={"value": [{"id": "a", "contentType": "application/octet-stream", "contentBytes": "AAH/"}]},
        )
        result = action.run({"user": "u", "message_id": "m"})
        assert result["errors"] == []
        assert result["attachments"][0]["base64_content"] == "AAH/"


def test_attachment_pagination_fails_explicitly_at_budget():
    graph = MailGraph(Mock())
    graph.page = Mock(return_value={"value": [], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"})
    with pytest.raises(RuntimeError, match="incomplete"):
        graph.attachments("u", "m")
    assert graph.page.call_count == 50


def test_large_retry_after_is_surfaced_not_shortened():
    response = Mock()
    response.getheader.return_value = "3600"
    with pytest.raises(InvalidHeader, match="budget"):
        Retry().get_retry_after(response)


def test_post_read_failures_are_not_retried_automatically():
    session = ApiClient(app_id="id", app_secret="fake", tenant_id="tenant")
    retry = session.get_adapter("https://").max_retries
    assert "POST" not in retry.allowed_methods
    assert "GET" in retry.allowed_methods


@pytest.mark.parametrize(
    "cls,name,args",
    [
        (ListMessagesAction, "action_list_messages", {"user": "u"}),
        (
            MoveMessageAction,
            "action_move_message",
            {"user": "u", "message_id": "old", "destination_folder": "junkemail"},
        ),
        (ExtractEmailAction, "action_extract_email", {"user": "u", "message_id": "old"}),
        (DownloadAttachmentsAction, "action_download_attachments", {"user": "u", "message_id": "old"}),
    ],
)
def test_new_actions_execute_through_real_sdk_and_match_result_schema(configured_action, cls, name, args):
    action = configured_action(cls)
    action.__dict__["client"] = requests.Session()
    action._arguments = args
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/inbox", json={"id": "inbox", "displayName": "Inbox"}
        )
        mock.get(
            "https://graph.microsoft.com/v1.0/users/u/mailFolders/junkemail",
            json={"id": "junk", "displayName": "Junk Email"},
        )
        mock.get("https://graph.microsoft.com/v1.0/users/u/mailFolders/inbox/messages", json={"value": []})
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/old/attachments", json={"value": []})
        mock.post("https://graph.microsoft.com/v1.0/users/u/messages/old/move", json={"id": "new"})
        mock.get("https://graph.microsoft.com/v1.0/users/u/messages/new", json={"parentFolderId": "junk"})
        with patch.object(action, "_send_request") as send:
            action.execute()
    payload = send.call_args.args[0]
    assert payload["status"] == "finished"
    assert "error" not in payload
    json.dumps(payload["results"])
    descriptor = json.loads((Path(__file__).parents[1] / f"{name}.json").read_text())
    jsonschema.validate(payload["results"], descriptor["results"])


@pytest.mark.parametrize("cls", [SearchMessagesAction, ListMessagesAction])
@pytest.mark.parametrize(
    "identifier", ["<MixedCase@sample.invalid", "MixedCase@sample.invalid>", "<<MixedCase@sample.invalid>>", "a\nb"]
)
def test_invalid_identifier_is_an_sdk_error_without_traceback_or_graph_request(configured_action, cls, identifier):
    action = configured_action(cls)
    client = Mock()
    action.__dict__["client"] = client
    action._arguments = {"user": "u", "email_message_id": identifier}
    with patch.object(action, "_send_request") as send:
        action.execute()
    payload = send.call_args.args[0]
    assert payload["status"] == "finished"
    assert payload["error"].startswith("Invalid email_message_id:")
    assert "Traceback" not in payload["error"]
    assert "unexpected error" not in payload["error"]
    assert identifier not in payload["error"]
    assert payload["results"]["outcome"] == "failed"
    assert payload["results"]["error_details"][0]["code"] == "invalid_arguments"
    client.get.assert_not_called()
    client.request.assert_not_called()
