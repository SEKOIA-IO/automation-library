from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_deploy_url_policy import DeployUrlPolicyAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = DeployUrlPolicyAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_deploy_url_policy_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post("https://my.fake.netskope.com/api/v2/policy/urllist/deploy", status_code=200, json={})

        result = action.run({"api_token": "fake_api_token"})

        assert result is None
        action.log.assert_any_call(level="info", message="Successfully deployed pending URL policy changes")
