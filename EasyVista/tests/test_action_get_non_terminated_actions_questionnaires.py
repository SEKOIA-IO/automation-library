import pytest
from helpers import RFC, assert_action_error, assert_action_success
from pydantic import ValidationError

from easyvista_modules.action.action_get_non_terminated_actions_questionnaires import (
    GetNonTerminatedActionsQuestionnaires,
)

ACTION_CASE = (
    GetNonTerminatedActionsQuestionnaires,
    {"current_incident": RFC, "action_type_id": 20},
    "GET",
    "/" + RFC + "/actions/questionnaire",
    {"record_count": 0, "total_record_count": 0, "results": []},
    {"record_count": 0, "total_record_count": 0, "results": []},
)


def test_action_success(make_action, requests_mock, api_url):
    assert_action_success(make_action, requests_mock, api_url, *ACTION_CASE)


def test_action_error(make_action, requests_mock, api_url):
    assert_action_error(make_action, requests_mock, api_url, *ACTION_CASE)


@pytest.mark.parametrize("cls", [GetNonTerminatedActionsQuestionnaires])
def test_questionnaire_type_is_numeric(make_action, requests_mock, cls):
    with pytest.raises(ValidationError):
        make_action(cls).run({"current_incident": RFC, "action_id": "31", "action_type_id": "guid"})
    assert not requests_mock.called
