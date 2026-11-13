import pytest

from easyvista_modules.action.action_create_related_action_incident import CreateRelatedActionIncident
from tests.helpers import RFC, TICKET, assert_action_error, assert_action_success

ACTION_CASE = (
    CreateRelatedActionIncident,
    {**TICKET, "action": {"action_type_id": "17", "group_id": 12}},
    "POST",
    "/" + RFC + "/actions",
    {"HREF": "ticket"},
    {"success": True, "status_code": 201, "href": "ticket"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("href", [None, "", 42])
def test_present_but_invalid_optional_href_fails(make_action, requests_mock, api_url, href):
    requests_mock.post(api_url + "/" + RFC + "/actions", status_code=201, json={"HREF": href})
    action = make_action(CreateRelatedActionIncident)
    assert action.run(ACTION_CASE[1]) is None
    action.error.assert_called_once_with("EasyVista API response must contain a non-empty string HREF")


@pytest.mark.parametrize("cls,nested", [(CreateRelatedActionIncident, True)])
@pytest.mark.parametrize("body", [{}, {"action_type_id": "17"}, {"group_id": 12}])
def test_workflow_identifiers_required(make_action, requests_mock, cls, nested, body):
    action = make_action(cls)
    assert action.run({**TICKET, **({"action": body} if nested else body)}) is None
    assert not requests_mock.called
    assert "Provide one of" in action.error.call_args.args[0]


@pytest.mark.parametrize("payload", [{}, None])
@pytest.mark.parametrize("cls,nested,path", [(CreateRelatedActionIncident, True, "actions")])
def test_workflow_optional_href(make_action, requests_mock, api_url, cls, nested, path, payload):
    if payload is None:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201)
    else:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201, json=payload)
    body = {"action_type_name": "Investigation", "group_mail": "soc@example.org"}
    result = make_action(cls).run({**TICKET, **({"action": body} if nested else body)})
    assert result == ({"success": True, "status_code": 201} if nested else {})
    assert requests_mock.last_request.json() == ({"action": body} if nested else body)
