from easyvista_modules.action.action_view_request_incident_problem import ViewRequestIncidentProblem
from tests.helpers import RFC, TICKET, assert_action_error, assert_action_success

ACTION_CASE = (
    ViewRequestIncidentProblem,
    TICKET,
    "GET",
    "/" + RFC + "/problem",
    {"records": [], "record_count": "0"},
    {"records": [], "record_count": "0"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)
