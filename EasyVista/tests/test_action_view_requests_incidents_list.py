from helpers import assert_action_error, assert_action_success

from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList

ACTION_CASE = (
    ViewRequestsIncidentsList,
    {},
    "GET",
    "",
    {"HREF": "query", "record_count": "0", "total_record_count": "0", "records": [], "@next": "next"},
    {"href": "query", "record_count": "0", "total_record_count": "0", "records": []},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


def test_list_query(make_action, requests_mock, api_url):
    requests_mock.get(api_url, json={"records": [], "record_count": "0"})
    args = {"max_rows": 10, "search": 'title:"SOC"', "sort": "submit_date_ut desc", "fields": "rfc_number"}
    make_action(ViewRequestsIncidentsList).run(args)
    assert requests_mock.last_request.qs == {key: [str(value).lower()] for key, value in args.items()}
    assert len(requests_mock.request_history) == 1
