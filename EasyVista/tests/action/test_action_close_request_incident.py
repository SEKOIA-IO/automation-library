import pytest

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from tests.helpers import RFC, TICKET, assert_action_error, assert_action_success

ACTION_CASE = (CloseRequestIncident, TICKET, "PUT", "/" + RFC + "/close", {"HREF": "ticket"}, {"href": "ticket"})


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("cls,extra", [(CloseRequestIncident, {})])
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


@pytest.mark.parametrize("delete,expected", [(True, 1), (False, 0)])
def test_close_mapping(make_action, requests_mock, api_url, delete, expected):
    requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.put(api_url + "/" + RFC + "/close", json={"HREF": "ticket"})
    make_action(CloseRequestIncident).run(
        {
            **TICKET,
            "delete_actions": delete,
            "status_guid": "guid",
            "comment": "Solved",
            "end_date": "01/01/2026 00:00:00",
            "catalog_guid": "cat",
        }
    )
    assert requests_mock.last_request.json() == {
        "DELETE_ACTIONS": expected,
        "STATUS_GUID": "guid",
        "COMMENT": "Solved",
        "END_DATE": "01/01/2026 00:00:00",
        "CATALOG_GUID": "cat",
    }


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
