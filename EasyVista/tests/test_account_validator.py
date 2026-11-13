import pytest

from easyvista_modules.account_validator import EasyVistaAccountValidator
from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList


@pytest.mark.parametrize("body", ["", "null", "[]", "42"])
def test_empty_or_non_object_response_invalidates_account(make_action, requests_mock, api_url, body):
    requests_mock.get(api_url, text=body)
    validator = make_action(EasyVistaAccountValidator)
    assert validator.validate() is False
    assert "empty or non-object response" in validator.error.call_args.args[0]


@pytest.mark.parametrize("cls", [ViewRequestsIncidentsList, EasyVistaAccountValidator])
@pytest.mark.parametrize(
    "config,expected",
    [
        ({"token": None}, "`token` is required when `use_token` is true"),
        ({"use_token": False}, "`username` and `password` are required when `use_token` is false"),
        ({"use_token": False, "username": "user"}, "`username` and `password` are required when `use_token` is false"),
        (
            {"use_token": False, "password": "password"},
            "`username` and `password` are required when `use_token` is false",
        ),
    ],
)
def test_conditional_credentials(make_action, requests_mock, cls, config, expected):
    action = make_action(cls, **config)
    if cls is EasyVistaAccountValidator:
        assert action.validate() is False
    else:
        assert action.run({}) is None
    action.error.assert_called_once_with(expected)
    assert not requests_mock.called


@pytest.mark.parametrize("status,valid", [(200, True), (401, False), (404, False), (590, False)])
def test_account_validator(make_action, requests_mock, api_url, status, valid):
    requests_mock.get(api_url, status_code=status, json={"records": []} if valid else {"error": "Unavailable"})
    validator = make_action(EasyVistaAccountValidator)
    assert validator.validate() is valid
    assert requests_mock.last_request.qs == {"max_rows": ["1"], "fields": ["rfc_number"]}


@pytest.mark.parametrize("status,valid", [(200, True), (403, False)])
def test_account_validator_falls_back_on_assets_when_requests_are_forbidden(
    make_action, requests_mock, api_url, status, valid
):
    requests_mock.get(api_url, status_code=403, json={"error": "Forbidden"})
    assets = requests_mock.get(
        api_url.replace("/requests", "/assets"),
        status_code=status,
        json={"records": []} if valid else {"error": "Forbidden"},
    )
    validator = make_action(EasyVistaAccountValidator)
    assert validator.validate() is valid
    assert assets.last_request.qs == {"max_rows": ["1"], "fields": ["asset_id"]}
    if not valid:
        assert "403 on GET /api/v1/00001/assets" in validator.error.call_args.args[0]
