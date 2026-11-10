from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_get_non_terminated_actions_questionnaires import (
    GetNonTerminatedActionsQuestionnaires,
)
from easyvista_modules.action.action_get_specific_action_questionnaire import GetSpecificActionQuestionnaire
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident

RFC = "I000000_000001"
TICKET = {"rfc_number": RFC}


def assert_action_success(make_action, requests_mock, api_url, cls, args, method, path, payload, expected):
    action = make_action(cls)
    if cls in (UpdateRequestIncident, CloseRequestIncident):
        requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    if isinstance(payload, bytes):
        requests_mock.register_uri(
            method, api_url + path, content=payload, headers={"Content-Type": "application/pdf"}
        )
    elif payload is None:
        requests_mock.register_uri(method, api_url + path, status_code=204)
    else:
        requests_mock.register_uri(method, api_url + path, json=payload, status_code=201 if method != "GET" else 200)
    assert action.run(args) == expected
    action.error.assert_not_called()
    if cls in (UpdateRequestIncident, CloseRequestIncident):
        assert [item.method for item in requests_mock.request_history] == ["GET", "PUT"]
    if cls in (GetNonTerminatedActionsQuestionnaires, GetSpecificActionQuestionnaire):
        assert requests_mock.last_request.qs == {"actiontypeid": ["20"]}


def assert_action_error(make_action, requests_mock, api_url, cls, args, method, path, payload, expected):
    action = make_action(cls)
    if cls in (UpdateRequestIncident, CloseRequestIncident):
        requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.register_uri(method, api_url + path, status_code=403, json={"error": "Denied"})
    assert action.run(args) is None
    assert "Denied" in action.error.call_args.args[0]
