import pytest
from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_suspend_request_incident import SuspendRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident

ACTION_CASE = (SuspendRequestIncident, TICKET, "PUT", "/" + RFC + "/suspend", {"HREF": "ticket"}, {"href": "ticket"})


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("cls,path,comment_key", [(SuspendRequestIncident, "suspend", "comment")])
def test_suspend_restart_mapping(make_action, requests_mock, api_url, cls, path, comment_key):
    requests_mock.put(api_url + "/" + RFC + "/" + path, json={"HREF": "ticket"})
    make_action(cls).run({**TICKET, "comment": "Wait", "done_by_id": 123})
    assert requests_mock.last_request.json() == {comment_key: "Wait", "done_by_id": 123}


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
