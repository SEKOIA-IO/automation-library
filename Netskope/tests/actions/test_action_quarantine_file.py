from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_quarantine_file import QuarantineFileAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = QuarantineFileAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_quarantine_file_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/quarantine", status_code=200, json={}
        )

        result = action.run({"api_token": "fake_api_token", "file_id": "file-123"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(level="info", message='Successfully quarantined file "file-123"')
