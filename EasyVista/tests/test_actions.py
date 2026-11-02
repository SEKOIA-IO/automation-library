import base64

import pytest
from pydantic import ValidationError

from easyvista.actions_documents import (
    DeleteRequestDocument,
    GetRequestIncidentDocument,
    GetRequestIncidentDocuments,
    UploadAttachDocumentRequestIncident,
)
from easyvista.actions_read import (
    GetNonTerminatedActionsQuestionnaires,
    GetSpecificActionQuestionnaire,
    ViewRequestIncident,
    ViewRequestIncidentComment,
    ViewRequestIncidentProblem,
    ViewRequestsIncidentsList,
)
from easyvista.actions_requests import (
    CloseRequestIncident,
    CreateRequestIncident,
    RestartRequestIncident,
    SuspendRequestIncident,
    UpdateRequestIncident,
)
from easyvista.actions_workflow import CreateRelatedActionIncident, CreateTaskRequestIncident

RFC = "I000000_000001"
TICKET = {"rfc_number": RFC}
CASES = [
    (
        CreateRequestIncident,
        {"requests": [{"title": "Alert"}]},
        "POST",
        "",
        {"HREF": "/requests/" + RFC},
        {"href": "/requests/" + RFC, "rfc_number": RFC},
    ),
    (
        UpdateRequestIncident,
        {**TICKET, "description": "Evidence"},
        "PUT",
        "/" + RFC,
        {"HREF": "ticket"},
        {"href": "ticket"},
    ),
    (CloseRequestIncident, TICKET, "PUT", "/" + RFC + "/close", {"HREF": "ticket"}, {"href": "ticket"}),
    (SuspendRequestIncident, TICKET, "PUT", "/" + RFC + "/suspend", {"HREF": "ticket"}, {"href": "ticket"}),
    (RestartRequestIncident, TICKET, "PUT", "/" + RFC + "/restart", {"HREF": "ticket"}, {"href": "ticket"}),
    (
        ViewRequestsIncidentsList,
        {},
        "GET",
        "",
        {"HREF": "query", "record_count": "0", "total_record_count": "0", "records": [], "@next": "next"},
        {"href": "query", "record_count": "0", "total_record_count": "0", "records": []},
    ),
    (
        ViewRequestIncident,
        TICKET,
        "GET",
        "/" + RFC,
        {"HREF": "ticket", "RFC_NUMBER": RFC},
        {"href": "ticket", "record": {"HREF": "ticket", "RFC_NUMBER": RFC}},
    ),
    (
        ViewRequestIncidentProblem,
        TICKET,
        "GET",
        "/" + RFC + "/problem",
        {"records": [], "record_count": "0"},
        {"records": [], "record_count": "0"},
    ),
    (
        ViewRequestIncidentComment,
        TICKET,
        "GET",
        "/" + RFC + "/comment",
        {"HREF": "comment", "PARENT_HREF": "ticket", "COMMENT": "first<br>second"},
        {"href": "comment", "parent_href": "ticket", "comment": "first<br>second"},
    ),
    (
        UploadAttachDocumentRequestIncident,
        {**TICKET, "documents": [{"filename": "report.txt", "filedata": "aGk="}]},
        "POST",
        "/" + RFC + "/documents",
        {"HREF": "ticket"},
        {"href": "ticket"},
    ),
    (
        GetRequestIncidentDocuments,
        TICKET,
        "GET",
        "/" + RFC + "/documents",
        {"PARENT_HREF": "ticket", "HREF": "documents", "Documents": [{"DOCUMENT_ID": "doc", "DOCUMENT": "a.txt"}]},
        {"parent_href": "ticket", "href": "documents", "documents": [{"DOCUMENT_ID": "doc", "DOCUMENT": "a.txt"}]},
    ),
    (
        GetRequestIncidentDocument,
        {**TICKET, "id": "doc"},
        "GET",
        "/" + RFC + "/documents/doc",
        b"\x00\xffhello",
        {"content_type": "application/pdf", "content_base64": base64.b64encode(b"\x00\xffhello").decode()},
    ),
    (
        DeleteRequestDocument,
        {**TICKET, "id": "doc"},
        "DELETE",
        "/" + RFC + "/documents/doc",
        None,
        {"success": True, "status_code": 204, "verified_by_listing": False, "message": "Document deleted"},
    ),
    (
        CreateRelatedActionIncident,
        {**TICKET, "action": {"action_type_id": "17", "group_id": 12}},
        "POST",
        "/" + RFC + "/actions",
        {"HREF": "ticket"},
        {"success": True, "status_code": 201, "href": "ticket"},
    ),
    (
        CreateTaskRequestIncident,
        {**TICKET, "action_type_id": "19", "group_name": "Support"},
        "POST",
        "/" + RFC + "/tasks",
        {"HREF": "task"},
        {"href": "task"},
    ),
    (
        GetNonTerminatedActionsQuestionnaires,
        {"current_incident": RFC, "action_type_id": 20},
        "GET",
        "/" + RFC + "/actions/questionnaire",
        {"record_count": 0, "total_record_count": 0, "results": []},
        {"record_count": 0, "total_record_count": 0, "results": []},
    ),
    (
        GetSpecificActionQuestionnaire,
        {"current_incident": RFC, "action_type_id": 20, "action_id": "31"},
        "GET",
        "/" + RFC + "/actions/31/questionnaire",
        {"record_count": 0, "total_record_count": 0, "results": []},
        {"record_count": 0, "total_record_count": 0, "results": []},
    ),
]


@pytest.mark.parametrize("cls,args,method,path,payload,expected", CASES, ids=[row[0].__name__ for row in CASES])
def test_action_success(make_action, requests_mock, api_url, cls, args, method, path, payload, expected):
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


@pytest.mark.parametrize("cls,args,method,path,payload,expected", CASES, ids=[row[0].__name__ for row in CASES])
def test_action_error(make_action, requests_mock, api_url, cls, args, method, path, payload, expected):
    action = make_action(cls)
    if cls in (UpdateRequestIncident, CloseRequestIncident):
        requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.register_uri(method, api_url + path, status_code=403, json={"error": "Denied"})
    assert action.run(args) is None
    assert "Denied" in action.error.call_args.args[0]


@pytest.mark.parametrize("cls,extra", [(UpdateRequestIncident, {"description": "new"}), (CloseRequestIncident, {})])
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


def test_create_mapping(make_action, requests_mock, api_url):
    action = make_action(CreateRequestIncident)
    requests_mock.post(api_url, json={"HREF": api_url + "/I%2Fexample?query=yes"})
    result = action.run(
        {
            "requests": [
                {
                    "title": "Explicit",
                    "catalog_code": "S_321",
                    "description": "Text",
                    "urgency_id": 2,
                    "impact_id": "1",
                    "recipient_name": "Recipient",
                    "recipient_mail": "user@example.org",
                    "department_code": "SOC",
                    "location_id": 7,
                    "custom_fields": {"title": "Ignored", "E_CUSTOM": "value", "E_NULL": None},
                }
            ]
        }
    )
    assert requests_mock.last_request.json() == {
        "requests": [
            {
                "TITLE": "Explicit",
                "Catalog_Code": "S_321",
                "Description": "Text",
                "Urgency_ID": 2,
                "IMPACT_ID": "1",
                "Recipient_Name": "Recipient",
                "Recipient_Mail": "user@example.org",
                "Department_Code": "SOC",
                "Location_ID": 7,
                "E_CUSTOM": "value",
            }
        ]
    }
    assert result["rfc_number"] == "I/example"


@pytest.mark.parametrize("items", [[], [{}, {}]])
def test_create_one_ticket_only(make_action, requests_mock, items):
    with pytest.raises(ValidationError):
        make_action(CreateRequestIncident).run({"requests": items})
    assert not requests_mock.called


def test_update_mapping_and_append(make_action, requests_mock, api_url):
    action = make_action(UpdateRequestIncident)
    requests_mock.get(api_url + "/" + RFC, json={"END_DATE_UT": ""})
    requests_mock.put(api_url + "/" + RFC, json={"HREF": "ticket"})
    action.run(
        {
            **TICKET,
            "append": True,
            "description": "New",
            "urgency_id": "2",
            "external_reference": "alert",
            "asset": "a",
            "asset_serial": "s",
            "ci": "c",
            "ci_id": 3,
            "custom_fields": {"description": "Ignored", "E_CUSTOM": "x"},
        }
    )
    assert requests_mock.last_request.qs == {"append": ["true"]}
    assert requests_mock.last_request.json() == {
        "Description": "New",
        "Urgency_ID": "2",
        "External_reference": "alert",
        "ASSET": "a",
        "ASSET_SERIAL": "s",
        "CI": "c",
        "CI_ID": 3,
        "E_CUSTOM": "x",
    }


@pytest.mark.parametrize("args", [TICKET, {**TICKET, "append": True}, {**TICKET, "custom_fields": {}}])
def test_update_empty(make_action, requests_mock, args):
    action = make_action(UpdateRequestIncident)
    assert action.run(args) is None
    assert not requests_mock.called
    assert "Nothing to update" in action.error.call_args.args[0]


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
    "cls,path,comment_key",
    [(SuspendRequestIncident, "suspend", "comment"), (RestartRequestIncident, "restart", "Comment")],
)
def test_suspend_restart_mapping(make_action, requests_mock, api_url, cls, path, comment_key):
    requests_mock.put(api_url + "/" + RFC + "/" + path, json={"HREF": "ticket"})
    make_action(cls).run({**TICKET, "comment": "Wait", "done_by_id": 123})
    assert requests_mock.last_request.json() == {comment_key: "Wait", "done_by_id": 123}


def test_list_query(make_action, requests_mock, api_url):
    requests_mock.get(api_url, json={"records": [], "record_count": "0"})
    args = {"max_rows": 10, "search": 'title:"SOC"', "sort": "submit_date_ut desc", "fields": "rfc_number"}
    make_action(ViewRequestsIncidentsList).run(args)
    assert requests_mock.last_request.qs == {key: [str(value).lower()] for key, value in args.items()}
    assert len(requests_mock.request_history) == 1


@pytest.mark.parametrize("description", [None, "", "Investigation"])
def test_upload_description(make_action, requests_mock, api_url, description):
    requests_mock.post(api_url + "/" + RFC + "/documents", json={"HREF": "ticket"})
    args = {**TICKET, "documents": [{"filename": "a.txt", "filedata": "aGk="}], "description": description}
    make_action(UploadAttachDocumentRequestIncident).run(args)
    body = requests_mock.last_request.json()
    assert body["documents"] == args["documents"]
    assert ("description" in body) == bool(description)
    if description:
        assert body["description"] == description


@pytest.mark.parametrize("filedata", ["not-base64!", "é", "data:text/plain;base64,aGk="])
def test_invalid_base64(make_action, requests_mock, filedata):
    action = make_action(UploadAttachDocumentRequestIncident)
    assert action.run({**TICKET, "documents": [{"filename": "a.txt", "filedata": filedata}]}) is None
    assert not requests_mock.called
    assert "not valid base64" in action.error.call_args.args[0]


@pytest.mark.parametrize(
    "status,documents,success",
    [
        (200, [], True),
        (200, [{"DOCUMENT_ID": "other"}], True),
        (200, [{"DOCUMENT_ID": "doc"}], False),
        (500, [], False),
        (200, None, False),
        (200, [{}], False),
    ],
)
def test_delete_590_verification(make_action, requests_mock, api_url, status, documents, success):
    action = make_action(DeleteRequestDocument)
    requests_mock.delete(
        api_url + "/" + RFC + "/documents/doc",
        status_code=590,
        json={"error": "Document was not found on the server."},
    )
    requests_mock.get(api_url + "/" + RFC + "/documents", status_code=status, json={"Documents": documents})
    result = action.run({**TICKET, "id": "doc"})
    assert [request.method for request in requests_mock.request_history] == ["DELETE", "GET"]
    if success:
        assert result["success"] and result["verified_by_listing"]
        assert result["status_code"] == 590
        assert result["api_error"] == "Document was not found on the server."
        action.error.assert_not_called()
        action.log.assert_called_once()
    else:
        assert result is None
        assert "590" in action.error.call_args.args[0]
        assert "verification did not confirm" in action.error.call_args.args[0]


@pytest.mark.parametrize("pagination", [{"@next": "next"}, {"total_record_count": 2}, {"total_record_count": "2"}])
def test_delete_590_incomplete_listing_does_not_confirm(make_action, requests_mock, api_url, pagination):
    action = make_action(DeleteRequestDocument)
    documents_url = api_url + "/" + RFC + "/documents"
    next_url = documents_url + "?offset=1"
    if "@next" in pagination:
        pagination = {"@next": next_url}
    requests_mock.delete(documents_url + "/doc", status_code=590, json={"error": "Deletion failed"})
    requests_mock.get(documents_url, json={"Documents": [{"DOCUMENT_ID": "other"}], **pagination})
    next_page = requests_mock.get(next_url, json={"Documents": [{"DOCUMENT_ID": "doc"}]})

    assert action.run({**TICKET, "id": "doc"}) is None
    assert [request.method for request in requests_mock.request_history] == ["DELETE", "GET"]
    assert not next_page.called
    message = action.error.call_args.args[0]
    assert "590" in message and "Deletion failed" in message
    assert "verification did not confirm" in message
    action.log.assert_not_called()


def test_delete_404_does_not_list(make_action, requests_mock, api_url):
    requests_mock.delete(api_url + "/" + RFC + "/documents/doc", status_code=404, json={"error": "Not found"})
    assert make_action(DeleteRequestDocument).run({**TICKET, "id": "doc"}) is None
    assert len(requests_mock.request_history) == 1


@pytest.mark.parametrize("cls,nested", [(CreateRelatedActionIncident, True), (CreateTaskRequestIncident, False)])
@pytest.mark.parametrize("body", [{}, {"action_type_id": "17"}, {"group_id": 12}])
def test_workflow_identifiers_required(make_action, requests_mock, cls, nested, body):
    action = make_action(cls)
    assert action.run({**TICKET, **({"action": body} if nested else body)}) is None
    assert not requests_mock.called
    assert "Provide one of" in action.error.call_args.args[0]


@pytest.mark.parametrize("payload", [{}, None])
@pytest.mark.parametrize(
    "cls,nested,path", [(CreateRelatedActionIncident, True, "actions"), (CreateTaskRequestIncident, False, "tasks")]
)
def test_workflow_optional_href(make_action, requests_mock, api_url, cls, nested, path, payload):
    if payload is None:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201)
    else:
        requests_mock.post(api_url + "/" + RFC + "/" + path, status_code=201, json=payload)
    body = {"action_type_name": "Investigation", "group_mail": "soc@example.org"}
    result = make_action(cls).run({**TICKET, **({"action": body} if nested else body)})
    assert result == ({"success": True, "status_code": 201} if nested else {})
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


@pytest.mark.parametrize("cls", [GetNonTerminatedActionsQuestionnaires, GetSpecificActionQuestionnaire])
def test_questionnaire_type_is_numeric(make_action, requests_mock, cls):
    with pytest.raises(ValidationError):
        make_action(cls).run({"current_incident": RFC, "action_id": "31", "action_type_id": "guid"})
    assert not requests_mock.called
