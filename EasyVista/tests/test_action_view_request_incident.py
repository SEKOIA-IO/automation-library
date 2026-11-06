from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_view_request_incident import ViewRequestIncident

ACTION_CASE = (
    ViewRequestIncident,
    TICKET,
    "GET",
    "/" + RFC,
    {"HREF": "ticket", "RFC_NUMBER": RFC},
    {"href": "ticket", "record": {"HREF": "ticket", "RFC_NUMBER": RFC}},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)
