from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_get_request_incident_documents import GetRequestIncidentDocuments

ACTION_CASE = (
    GetRequestIncidentDocuments,
    TICKET,
    "GET",
    "/" + RFC + "/documents",
    {"PARENT_HREF": "ticket", "HREF": "documents", "Documents": [{"DOCUMENT_ID": "doc", "DOCUMENT": "a.txt"}]},
    {"parent_href": "ticket", "href": "documents", "documents": [{"DOCUMENT_ID": "doc", "DOCUMENT": "a.txt"}]},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)
