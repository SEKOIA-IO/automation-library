"""Validate analyst-visible errors and reliable playbook outcomes through the SDK."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import jsonschema
import pytest
import requests

from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_download_attachments import DownloadAttachmentsAction
from microsoft_outlook_modules.action_extract_email import ExtractEmailAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_list_messages import ListMessagesAction
from microsoft_outlook_modules.action_move_message import MoveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.action_send_message import SendMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction
from microsoft_outlook_modules.errors import describe_error

CASES = [
    (DeleteMessageAction, "action_delete_message", {"message_id": "m"}),
    (DownloadAttachmentsAction, "action_download_attachments", {"message_id": "m"}),
    (ExtractEmailAction, "action_extract_email", {"message_id": "m"}),
    (ForwardMessageAction, "action_forward_message", {"message_id": "m", "recipients": ["recipient@example.com"]}),
    (GetMessageAction, "action_get_message", {"message_id": "m"}),
    (ListMessagesAction, "action_list_messages", {}),
    (MoveMessageAction, "action_move_message", {"message_id": "m", "destination_folder": "junkemail"}),
    (SearchMessagesAction, "action_search_messages", {"email_message_id": "<id@example.com>"}),
    (
        SendMessageAction,
        "action_send_message",
        {
            "sender": "sender@example.com",
            "from": "sender@example.com",
            "recipients": ["recipient@example.com"],
            "subject": "Test",
            "content": "Test",
        },
    ),
    (UpdateMessageAction, "action_update_message", {"message_id": "m", "subject": "Changed"}),
]


def execute(action, arguments):
    action._arguments = arguments
    with patch.object(action, "_send_request") as send:
        action.execute()
    return send.call_args.args[0]


def http_error(status):
    response = requests.Response()
    response.status_code = status
    response.url = "https://graph.microsoft.com/v1.0/users/u/messages/m"
    response._content = b'{"error":{"code":"BadRequest","message":"private-body-marker"}}'
    return requests.HTTPError("private-exception-marker", response=response)


def failing_client(exc):
    client = Mock()
    for name in ["get", "post", "delete", "patch", "request"]:
        getattr(client, name).side_effect = exc
    return client


@pytest.mark.parametrize("cls,name,args", CASES)
def test_all_actions_report_invalid_arguments_without_calling_graph(configured_action, cls, name, args):
    action = configured_action(cls)
    client = Mock()
    action.__dict__["client"] = client
    payload = execute(action, {})
    assert payload["results"]["outcome"] == "failed"
    assert payload["results"]["error_details"][0]["code"] == "invalid_arguments"
    assert "Invalid parameters" in payload["error"]
    assert "Traceback" not in payload["error"]
    assert client.mock_calls == []


@pytest.mark.parametrize(
    "identifiers",
    [
        {},
        {"email_message_id": "", "email_local_id": ""},
        {"email_message_id": None, "email_local_id": None},
        {"email_message_id": " \t", "email_local_id": "\n "},
    ],
)
def test_empty_search_identifiers_return_actionable_error_through_sdk(configured_action, identifiers):
    action = configured_action(SearchMessagesAction)
    client = Mock()
    action.__dict__["client"] = client
    payload = execute(action, {"user": "u", **identifiers})
    assert payload["results"]["outcome"] == "failed"
    assert payload["results"]["error_details"][0]["code"] == "invalid_arguments"
    assert "Either email_message_id or email_local_id" in payload["error"]
    assert "List messages in a folder" in payload["error"]
    assert "Unexpected error" not in payload["error"]
    assert "Traceback" not in payload["error"]
    assert client.mock_calls == []


def test_search_descriptor_allows_missing_identifier_to_reach_action_validation(configured_action):
    descriptor = json.loads((Path(__file__).parents[1] / "action_search_messages.json").read_text())
    arguments = {"user": "u"}
    jsonschema.validate(arguments, descriptor["arguments"])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, descriptor["arguments"])
    action = configured_action(SearchMessagesAction)
    payload = execute(action, arguments)
    assert payload["error"].startswith("Invalid parameters:")
    assert "List messages in a folder" in payload["error"]


@pytest.mark.parametrize("cls,name,args", CASES)
@pytest.mark.parametrize(
    "status,code",
    [
        (400, "request_rejected"),
        (401, "authentication_failed"),
        (403, "access_denied"),
        (404, "not_found"),
        (409, "conflict"),
        (410, "resource_expired"),
        (429, "rate_limited"),
        (503, "service_unavailable"),
    ],
)
def test_all_actions_report_http_errors_without_response_body_or_traceback(
    configured_action, cls, name, args, status, code
):
    action = configured_action(cls)
    action.__dict__["client"] = failing_client(http_error(status))
    payload = execute(action, {"user": "u", **args})
    result = payload["results"]
    assert result["outcome"] in {"failed", "unknown"}
    assert result["error_details"][0]["code"] == code
    assert result["error_details"][0]["http_status"] == status
    assert payload["error"]
    encoded = json.dumps(payload)
    for forbidden in ["Traceback", "private-body-marker", "private-exception-marker"]:
        assert forbidden not in encoded
    descriptor = json.loads((Path(__file__).parents[1] / f"{name}.json").read_text())
    jsonschema.validate(result, descriptor["results"])


@pytest.mark.parametrize("cls,name,args", CASES)
@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_network_errors_are_safe_and_writes_are_not_blindly_retryable(configured_action, cls, name, args, exception):
    action = configured_action(cls)
    action.__dict__["client"] = failing_client(exception("private-network-marker"))
    payload = execute(action, {"user": "u", **args})
    uncertain = action.may_modify_data and cls is not MoveMessageAction  # Move fails while looking up destination.
    assert payload["results"]["outcome"] == ("unknown" if uncertain else "failed")
    detail = payload["results"]["error_details"][0]
    assert detail["retryable"] is not uncertain
    assert "private-network-marker" not in json.dumps(payload)
    assert "Traceback" not in payload["error"]


@pytest.mark.parametrize(
    "cls,name,args", [case for case in CASES if case[0] in {ExtractEmailAction, DownloadAttachmentsAction}]
)
@pytest.mark.parametrize("partial", [True, False])
def test_attachment_errors_keep_partial_results_and_fail_the_sdk_action(configured_action, cls, name, args, partial):
    action = configured_action(cls)
    detail = {"code": "not_found", "message": "Attachment not found.", "retryable": False, "outcome_unknown": False}
    attachments = [{"attachment_id": "good", "base64_content": "YQ=="}] if partial else []
    parsed = [{"subject": "Recovered original"}] if partial else []
    with patch(f"microsoft_outlook_modules.{name}.collect_attachments", return_value=(attachments, parsed, [detail])):
        payload = execute(action, {"user": "u", **args})
    assert payload["results"]["outcome"] == ("partial" if partial else "failed")
    assert payload["results"]["attachments"] == attachments
    assert payload["error"]
    assert payload["results"]["error_details"] == [detail]


def test_unexpected_failure_has_a_safe_diagnostic_reference(configured_action):
    action = configured_action(GetMessageAction)
    action.__dict__["client"] = failing_client(RuntimeError("private-unexpected-marker"))
    payload = execute(action, {"user": "u", "message_id": "m"})
    detail = payload["results"]["error_details"][0]
    assert detail["code"] == "unexpected_error"
    assert detail["diagnostic_reference"] in payload["error"]
    assert detail["diagnostic_reference"] in payload["logs"]
    assert "private-unexpected-marker" not in json.dumps(payload)
    assert "Traceback" not in payload["error"]


def test_successful_reuse_does_not_keep_a_previous_validation_error(configured_action):
    action = configured_action(SearchMessagesAction)
    assert action.run({"user": "u"})["outcome"] == "failed"
    client = Mock()
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"value":[]}'
    client.get.return_value = response
    action.__dict__["client"] = client
    assert action.run({"user": "u", "email_message_id": "id@example.com"})["outcome"] == "succeeded"
    assert not action.error_message


def test_oauth_bad_request_is_authentication_failure():
    error = http_error(400)
    error.response.url = "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
    assert describe_error(error)["code"] == "authentication_failed"


@pytest.mark.parametrize(
    "scenario,outcome",
    [
        ("verified", "succeeded"),
        ("mismatch", "partial"),
        ("verification_timeout", "unknown"),
        ("missing_id", "unknown"),
        ("move_timeout", "unknown"),
        ("move_forbidden", "failed"),
    ],
)
def test_move_sdk_error_preserves_execution_and_verification_state(configured_action, scenario, outcome):
    action = configured_action(MoveMessageAction)
    action.__dict__["client"] = Mock()
    graph = Mock()
    graph.folder.return_value = {"id": "junk", "displayName": "Junk Email"}
    if scenario == "move_timeout":
        graph.json.side_effect = requests.Timeout("private-move-marker")
    elif scenario == "move_forbidden":
        graph.json.side_effect = http_error(403)
    else:
        verification = (
            requests.Timeout("private-verification-marker")
            if scenario == "verification_timeout"
            else {"parentFolderId": "inbox" if scenario == "mismatch" else "junk"}
        )
        graph.json.side_effect = [{} if scenario == "missing_id" else {"id": "new"}, verification]
    with patch("microsoft_outlook_modules.action_move_message.MailGraph", return_value=graph):
        payload = execute(action, {"user": "u", "message_id": "old", "destination_folder": "junkemail"})
    result = payload["results"]
    assert result["outcome"] == outcome
    assert bool(payload.get("error")) is (outcome != "succeeded")
    assert result["execution_status"] == ("failed_or_unknown" if scenario.startswith("move_") else "succeeded")
    assert all(not error["retryable"] for error in result["error_details"])
    assert "private-" not in json.dumps(payload)
    assert graph.json.call_count <= 2


def test_scan_budget_exhaustion_keeps_results_but_marks_search_partial(configured_action):
    action = configured_action(SearchMessagesAction)
    response = requests.Response()
    response.status_code = 400
    response._content = b'{"error":{"code":"InefficientFilter"}}'
    client = Mock()
    client.get.return_value = response
    action.__dict__["client"] = client
    with patch.object(
        action,
        "_search_messages_fallback",
        return_value={
            "value": [{"id": "found", "internetMessageId": "<id@example.com>"}],
            "fallback_has_more": True,
            "scan_limit_reached": True,
        },
    ):
        payload = execute(action, {"user": "u", "email_message_id": "id@example.com"})
    assert payload["results"]["outcome"] == "partial"
    assert payload["results"]["message_ids"] == ["found"]
    assert payload["results"]["error_details"][0]["code"] == "incomplete_results"
    assert payload["error"]


@pytest.mark.parametrize(
    "status,expected_code,retryable",
    [
        (400, "authentication_failed", False),
        (401, "authentication_failed", False),
        (403, "authentication_failed", False),
        (429, "rate_limited", True),
        (500, "service_unavailable", True),
        (502, "service_unavailable", True),
        (503, "service_unavailable", True),
    ],
)
def test_oauth_transient_failures_are_distinct_from_invalid_credentials(status, expected_code, retryable):
    response = requests.Response()
    response.status_code = status
    response.url = "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
    detail = describe_error(requests.HTTPError(response=response))
    assert detail["code"] == expected_code
    assert detail["retryable"] is retryable
    assert detail["outcome_unknown"] is False
