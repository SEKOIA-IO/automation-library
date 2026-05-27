from unittest.mock import MagicMock

import pytest
import requests_mock
from pydantic import ValidationError

from netskope_modules.actions.action_replace_blocklist import ReplaceBlocklistAction


@pytest.fixture
def replace_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = ReplaceBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_replace_blocklist_success(replace_action):
    """Test successful replacement of blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/456/replace",
            status_code=200,
            json={
                "data": {"type": "exact", "urls": ["new-blocked.com", "another-blocked.com"]},
                "id": 456,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Edited",
                "name": "Updated Blocklist",
                "pending": 1,
            },
        )

        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[
                {
                    "data": {"type": "exact", "urls": ["new-blocked.com", "another-blocked.com"]},
                    "id": 456,
                    "modify_by": "Netskope API",
                    "modify_time": "1997-01-01 00:00:00",
                    "modify_type": "Created",
                    "name": "Updated Blocklist",
                    "pending": 0,
                }
            ],
        )

        arguments = {
            "url_list_id": "456",
            "items": ["new-blocked.com", "another-blocked.com"],
            "name": "Updated Blocklist",
            "type": "exact",
        }

        result = replace_action.run(arguments)

        assert result["replace_result"]["id"] == 456
        assert result["replace_result"]["name"] == "Updated Blocklist"
        assert len(result["deploy_result"]) == 1
        assert result["deploy_result"][0]["pending"] == 0
        assert "Successfully replaced blocklist with 2 item(s)" in result["message"]


def test_replace_blocklist_missing_required_params(replace_action):
    """Test that replace action fails when required parameters are missing"""
    arguments = {
        "url_list_id": "456",
        "items": ["new-blocked.com"],
    }

    with pytest.raises(ValidationError):
        # Missing field 'name' should cause validation error
        replace_action.run(arguments)
