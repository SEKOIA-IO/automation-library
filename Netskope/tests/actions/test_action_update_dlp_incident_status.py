from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_update_dlp_incident_status import UpdateDlpIncidentStatusAction


@pytest.fixture
def action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = UpdateDlpIncidentStatusAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_update_dlp_incident_status_success(action):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch("https://my.fake.netskope.com/api/v2/dlp/incident/inc-123", status_code=200, json={})

        result = action.run(
            {
                "api_token": "fake_api_token",
                "incident_id": "inc-123",
                "status": "closed",
                "notes": "Remediated by playbook",
            }
        )

        assert result is None
        assert mock_requests.request_history[0].json() == {"status": "closed", "notes": "Remediated by playbook"}
        action.log.assert_any_call(level="info", message='Successfully updated DLP incident "inc-123" to "closed"')
