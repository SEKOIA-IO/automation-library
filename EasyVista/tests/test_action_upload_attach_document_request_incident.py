import pytest
from helpers import RFC, TICKET, assert_action_error, assert_action_success

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from easyvista_modules.action.action_upload_attach_document_request_incident import UploadAttachDocumentRequestIncident

ACTION_CASE = (
    UploadAttachDocumentRequestIncident,
    {**TICKET, "documents": [{"filename": "report.txt", "filedata": "aGk="}]},
    "POST",
    "/" + RFC + "/documents",
    {"HREF": "ticket"},
    {"href": "ticket"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


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
