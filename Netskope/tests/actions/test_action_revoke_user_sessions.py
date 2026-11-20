from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_revoke_user_sessions import RevokeUserSessionsAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = RevokeUserSessionsAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_revoke_user_sessions_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post("https://my.fake.netskope.com/api/v2/events/token/revoke", status_code=200, json={})

        result = action.run({"api_token": "fake_api_token", "user_name": "alice@example.com"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"userName": "alice@example.com"}
        action.log.assert_any_call(
            level="info", message='Successfully revoked active Netskope sessions for "alice@example.com"'
        )
