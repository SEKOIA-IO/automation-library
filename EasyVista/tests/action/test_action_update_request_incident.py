from io import BytesIO
from unittest.mock import patch

import pytest
from urllib3.response import HTTPResponse

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from tests.helpers import RFC, TICKET, assert_action_error, assert_action_success

ACTION_CASE = (
    UpdateRequestIncident,
    {**TICKET, "description": "Evidence"},
    "PUT",
    "/" + RFC,
    {"HREF": "ticket"},
    {"href": "ticket"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("cls,extra", [(UpdateRequestIncident, {"description": "new"})])
@pytest.mark.parametrize("closed,status", [(True, 200), (False, 404)])
def test_precheck_failure(make_action, requests_mock, api_url, cls, extra, closed, status):
    action = make_action(cls)
    requests_mock.get(
        api_url + "/" + RFC,
        status_code=status,
        json={"END_DATE_UT": "2026-01-01"} if closed else {"error": "Resource not found"},
    )
    assert action.run({**TICKET, **extra}) is None
    assert len(requests_mock.request_history) == 1
    assert ("already closed" if closed else "Resource not found") in action.error.call_args.args[0]


@pytest.mark.parametrize("append", [False, None])
def test_update_replace_omits_append_query(make_action, requests_mock, api_url, append):
    action = make_action(UpdateRequestIncident)
    requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.put(api_url + "/" + RFC, json={"HREF": "ticket"})
    arguments = {**TICKET, "description": "New"} | ({"append": append} if append is not None else {})
    assert action.run(arguments) == {"href": "ticket"}
    assert requests_mock.last_request.qs == {}
    assert requests_mock.last_request.json() == {"Description": "New"}


def test_update_mapping_and_append(make_action, requests_mock, api_url):
    action = make_action(UpdateRequestIncident)
    requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.put(api_url + "/" + RFC, json={"HREF": "ticket"})
    action.run(
        {
            **TICKET,
            "append": True,
            "description": "New",
            "urgency_id": "2",
            "external_reference": "alert",
            "asset": "a",
            "asset_serial": "s",
            "ci": "c",
            "ci_id": 3,
            "custom_fields": {"description": "Ignored", "E_CUSTOM": "x"},
        }
    )
    assert requests_mock.last_request.qs == {"append": ["true"]}
    assert requests_mock.last_request.json() == {
        "Description": "New",
        "Urgency_ID": "2",
        "External_reference": "alert",
        "ASSET": "a",
        "ASSET_SERIAL": "s",
        "CI": "c",
        "CI_ID": 3,
        "E_CUSTOM": "x",
    }


@pytest.mark.parametrize("custom_fields", [{}, {"Description": "From custom fields"}, {"Description": ""}])
def test_update_ignores_empty_playbook_defaults(make_action, requests_mock, api_url, custom_fields):
    action = make_action(UpdateRequestIncident)
    requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.put(api_url + "/" + RFC, json={"HREF": "ticket"})
    action.run(
        {
            **TICKET,
            "description": "",
            "urgency_id": "2",
            "external_reference": "",
            "asset": "",
            "asset_serial": "",
            "ci": "",
            "ci_id": 0,
            "custom_fields": custom_fields,
        }
    )
    assert requests_mock.last_request.json() == {"Urgency_ID": "2", "CI_ID": 0, **custom_fields}
    action.error.assert_not_called()


def test_update_only_empty_playbook_defaults_is_rejected(make_action, requests_mock):
    action = make_action(UpdateRequestIncident)
    assert (
        action.run(
            {
                **TICKET,
                "description": "",
                "urgency_id": "",
                "external_reference": "",
                "asset": "",
                "asset_serial": "",
                "ci": "",
            }
        )
        is None
    )
    assert not requests_mock.called
    action.error.assert_called_once_with("Nothing to update: provide at least one field")


@pytest.mark.parametrize("args", [TICKET, {**TICKET, "append": True}, {**TICKET, "custom_fields": {}}])
def test_update_empty(make_action, requests_mock, args):
    action = make_action(UpdateRequestIncident)
    assert action.run(args) is None
    assert not requests_mock.called
    assert "Nothing to update" in action.error.call_args.args[0]


@pytest.mark.parametrize(
    "payload", [{}, {"HREF": None}, {"HREF": ""}, {"HREF": "   "}, {"HREF": 42}, {"HREF": []}, None]
)
def test_required_href_rejects_invalid_response(make_action, requests_mock, api_url, payload):
    cls, args, method, path, _, _ = ACTION_CASE
    action = make_action(cls)
    if cls in (UpdateRequestIncident, CloseRequestIncident):
        requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    if payload is None:
        requests_mock.register_uri(method, api_url + path, status_code=201)
    else:
        requests_mock.register_uri(method, api_url + path, status_code=201, json=payload)
    assert action.run(args) is None
    action.error.assert_called_once()
    assert "HREF" in action.error.call_args.args[0]


@pytest.mark.parametrize("status", [502, 503, 504])
@pytest.mark.parametrize("append,attempts", [(True, 1), (False, 3)])
def test_append_updates_are_not_retried(make_action, monkeypatch, api_url, status, append, attempts):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(UpdateRequestIncident)
    methods = []

    def reply(conn, method, url, **kwargs):
        methods.append(method)
        return HTTPResponse(
            status=200 if method == "GET" else status,
            body=BytesIO(b'{"END_DATE_UT":""}' if method == "GET" else b'{"error":"gateway error"}'),
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    with patch("urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=reply):
        with patch("urllib3.util.retry.time.sleep"):
            assert action.run({"rfc_number": "ticket", "description": "Evidence", "append": append}) is None
    assert methods == ["GET"] + ["PUT"] * attempts
    assert f"EasyVista API error {status}" in action.error.call_args.args[0]
