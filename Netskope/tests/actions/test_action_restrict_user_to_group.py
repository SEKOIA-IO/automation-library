import re
from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_restrict_user_to_group import RestrictUserToGroupAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = RestrictUserToGroupAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_restrict_user_to_group_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/scim/Users",
            status_code=200,
            json={"Resources": [{"id": "user-123", "userName": "alice@example.com"}]},
        )
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/scim/Users/user-123", status_code=200, json={"id": "user-123"}
        )

        result = action.run(
            {"api_token": "fake_api_token", "user_name": "alice@example.com", "group_ids": ["group-1", "group-2"]}
        )

        assert result is None
        assert mock_requests.request_history[1].json() == {"groups": [{"value": "group-1"}, {"value": "group-2"}]}
        action.log.assert_any_call(
            level="info",
            message='Successfully restricted Netskope user "alice@example.com" (id = user-123) to 2 group(s)',
        )


@pytest.mark.parametrize(
    "search_result,expected_error",
    [
        ({"Resources": []}, 'Unable to find Netskope user for userName "alice@example.com"'),
        (
            {"Resources": [{"userName": "alice@example.com"}]},
            'Unable to find Netskope user identifier for userName "alice@example.com"',
        ),
    ],
)
def test_restrict_user_to_group_unresolved_user(action, search_result, expected_error):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://my.fake.netskope.com/api/v2/scim/Users", status_code=200, json=search_result)

        with pytest.raises(ValueError, match=re.escape(expected_error)):
            action.run({"api_token": "fake_api_token", "user_name": "alice@example.com", "group_ids": ["group-1"]})

        # No group assignment must be attempted for an unresolved user
        assert [request.method for request in mock_requests.request_history] == ["GET"]
