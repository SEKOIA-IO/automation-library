from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_view_request_incident_comment import ViewRequestIncidentComment

ACTION_CASE = (
    ViewRequestIncidentComment,
    TICKET,
    "GET",
    "/" + RFC + "/comment",
    {"HREF": "comment", "PARENT_HREF": "ticket", "COMMENT": "first<br>second"},
    {"href": "comment", "parent_href": "ticket", "comment": "first<br>second"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)
