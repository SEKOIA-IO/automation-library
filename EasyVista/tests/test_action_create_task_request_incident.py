import pytest
from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_create_task_request_incident import CreateTaskRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident

ACTION_CASE = (
    CreateTaskRequestIncident,
    {**TICKET, "action_type_id": "19", "group_name": "Support"},
    "POST",
    "/" + RFC + "/tasks",
    {"HREF": "task"},
    {"href": "task"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("cls,nested", [(CreateTaskRequestIncident, False)])
@pytest.mark.parametrize("body", [{}, {"action_type_id": "17"}, {"group_id": 12}])
def test_workflow_identifiers_required(make_action, requests_mock, cls, nested, body):
    action = make_action(cls)
    assert action.run({**TICKET, **({"action": body} if nested else body)}) is None
    assert not requests_mock.called
    assert "Provide one of" in action.error.call_args.args[0]


@pytest.mark.parametrize("payload", [{}, None])
@pytest.mark.parametrize("cls,nested,path", [(CreateTaskRequestIncident, False, "tasks")])
def test_task_missing_href_fails(make_action, requests_mock, api_url, cls, nested, path, payload):
    if payload is None:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201)
    else:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201, json=payload)
    body = {"action_type_name": "Investigation", "group_mail": "soc@example.org"}
    result = make_action(cls).run({**TICKET, **({"action": body} if nested else body)})
    assert result is None
    assert requests_mock.last_request.json() == ({"action": body} if nested else body)


def test_task_elapsed_time(make_action, requests_mock, api_url):
    requests_mock.post(api_url + "/" + RFC + "/tasks", json={"HREF": "task"})
    make_action(CreateTaskRequestIncident).run(
        {
            **TICKET,
            "action_type_id": "19",
            "group_name": "SOC",
            "elapsed_time": "60",
            "time_cost": "2",
            "contractual_cost": "3",
            "creation_date_ut": "created",
            "start_date_ut": "start",
            "end_date_ut": "end",
            "description": "Investigate",
        }
    )
    assert requests_mock.last_request.json() == {
        "action_type_id": "19",
        "group_name": "SOC",
        "Elapsed_Time": "60",
        "time_cost": "2",
        "contractual_cost": "3",
        "creation_date_ut": "created",
        "start_date_ut": "start",
        "end_date_ut": "end",
        "description": "Investigate",
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
