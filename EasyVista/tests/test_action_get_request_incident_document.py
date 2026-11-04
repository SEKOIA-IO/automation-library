import base64

import pytest
from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_get_request_incident_document import GetRequestIncidentDocument

ACTION_CASE = (
    GetRequestIncidentDocument,
    {**TICKET, "id": "doc"},
    "GET",
    "/" + RFC + "/documents/doc",
    b"\x00\xffhello",
    {"content_type": "application/pdf", "content_base64": base64.b64encode(b"\x00\xffhello").decode()},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("content_type", ["application/json", "application/octet-stream"])
def test_download_json_with_error_key_is_file_content(make_action, requests_mock, api_url, content_type):
    content = b'{"error":"investigation evidence", "events": []}'
    requests_mock.get(api_url + "/" + RFC + "/documents/doc", content=content, headers={"Content-Type": content_type})
    action = make_action(GetRequestIncidentDocument)
    assert action.run({**TICKET, "id": "doc"}) == {
        "content_type": content_type,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
    action.error.assert_not_called()


@pytest.mark.parametrize("status", [401, 404, 590])
def test_download_api_error_is_still_reported(make_action, requests_mock, api_url, status):
    requests_mock.get(
        api_url + "/" + RFC + "/documents/doc", status_code=status, json={"error": "Document unavailable"}
    )
    action = make_action(GetRequestIncidentDocument)
    assert action.run({**TICKET, "id": "doc"}) is None
    assert f"EasyVista API error {status}" in action.error.call_args.args[0]
    assert "Document unavailable" in action.error.call_args.args[0]
