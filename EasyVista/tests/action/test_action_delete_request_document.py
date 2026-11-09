import pytest

from easyvista_modules.action.action_delete_request_document import DeleteRequestDocument
from tests.helpers import RFC, TICKET, assert_action_error, assert_action_success

ACTION_CASE = (
    DeleteRequestDocument,
    {**TICKET, "id": "doc"},
    "DELETE",
    "/" + RFC + "/documents/doc",
    None,
    {"success": True, "status_code": 204, "verified_by_listing": False, "message": "Document deleted"},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize(
    "status,documents,success",
    [
        (200, [], True),
        (200, [{"DOCUMENT_ID": "other"}], True),
        (200, [{"DOCUMENT_ID": "doc"}], False),
        (500, [], False),
        (200, None, False),
        (200, [{}], False),
        (200, [{"DOCUMENT_ID": None}], False),
        (200, [{"DOCUMENT_ID": ""}], False),
        (200, [{"DOCUMENT_ID": " \t"}], False),
        (200, [{"DOCUMENT_ID": []}], False),
        (200, [{"DOCUMENT_ID": {}}], False),
        (200, [{"DOCUMENT_ID": True}], False),
        (200, [{"DOCUMENT_ID": False}], False),
        (200, [{"DOCUMENT_ID": 1.5}], False),
        (200, [{"DOCUMENT_ID": 123}], True),
        (200, [{"DOCUMENT_ID": 0}], True),
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


def test_delete_590_integer_id_still_present(make_action, requests_mock, api_url):
    action = make_action(DeleteRequestDocument)
    url = api_url + "/" + RFC + "/documents"
    requests_mock.delete(url + "/123", status_code=590, json={"error": "Deletion failed"})
    requests_mock.get(url, json={"Documents": [{"DOCUMENT_ID": 123}]})
    assert action.run({**TICKET, "id": "123"}) is None
    assert "verification did not confirm" in action.error.call_args.args[0]


def test_delete_590_redacts_nested_message_in_result_and_log(make_action, requests_mock, api_url):
    secret = 'sécret-"quoted"-\\value'
    action = make_action(DeleteRequestDocument, password=secret)
    url = api_url + "/" + RFC + "/documents"
    requests_mock.delete(url + "/doc", status_code=590, json={"message": {"details": [secret]}})
    requests_mock.get(url, json={"Documents": []})
    result = action.run({**TICKET, "id": "doc"})
    assert result["success"] is True
    for message in (result["api_error"], result["message"], action.log.call_args.kwargs["message"]):
        assert "[REDACTED]" in message
        assert "cret" not in message
