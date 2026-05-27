from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_delete_blocklist import DeleteBlocklistAction


@pytest.fixture
def delete_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = DeleteBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_delete_blocklist_success(delete_action):
    """Test successful deletion of a blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.delete(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={
                "data": {"type": "exact", "urls": ["www.test.com"]},
                "id": 0,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Deleted",
                "name": "string",
                "pending": 1,
            },
        )

        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[
                {
                    "data": {"type": "exact", "urls": ["www.test.com"]},
                    "id": 0,
                    "modify_by": "Netskope API",
                    "modify_time": "1997-01-01 00:00:00",
                    "modify_type": "Created",
                    "name": "string",
                    "pending": 0,
                }
            ],
        )

        arguments = {"id": 123}

        result = delete_action.run(arguments)

        assert result["delete_result"]["modify_type"] == "Deleted"
        assert result["delete_result"]["pending"] == 1
        assert len(result["deploy_result"]) == 1
        assert result["deploy_result"][0]["pending"] == 0
        assert "Successfully deleted blocklist 123" in result["message"]
