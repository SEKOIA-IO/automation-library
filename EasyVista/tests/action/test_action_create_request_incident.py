import pytest
from pydantic import ValidationError

from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_create_request_incident import CreateRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from tests.helpers import RFC, assert_action_error, assert_action_success

ACTION_CASE = (
    CreateRequestIncident,
    {"requests": [{"title": "Alert"}]},
    "POST",
    "",
    {"HREF": "/requests/" + RFC},
    {"href": "/requests/" + RFC, "rfc_number": RFC},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


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
