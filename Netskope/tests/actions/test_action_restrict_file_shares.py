from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_restrict_file_shares import RestrictFileSharesAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = RestrictFileSharesAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_restrict_file_shares_unshare_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/unshare", status_code=200, json={}
        )

        result = action.run({"api_token": "fake_api_token", "file_id": "file-123"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(
            level="info", message='Successfully applied "unshare" remediation to file "file-123"'
        )


def test_restrict_file_shares_restrict_access_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/restrict-access", status_code=200, json={}
        )

        result = action.run({"api_token": "fake_api_token", "file_id": "file-123", "operation": "restrict-access"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(
            level="info", message='Successfully applied "restrict-access" remediation to file "file-123"'
        )
