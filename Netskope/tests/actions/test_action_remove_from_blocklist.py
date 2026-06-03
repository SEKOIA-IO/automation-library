from unittest.mock import MagicMock

import pytest
import requests_mock

from netskope_modules.actions.action_remove_from_blocklist import RemoveFromBlocklistAction


@pytest.fixture
def remove_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = RemoveFromBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_remove_from_blocklist_success(remove_action):
    """Test successful removal of items from a blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            [
                {
                    "status_code": 200,
                    "json": {
                        "data": {"type": "exact", "urls": ["www.test.com"]},
                        "id": 123,
                        "modify_by": "Netskope API",
                        "modify_time": "1997-01-01 00:00:00",
                        "modify_type": "Edited",
                        "name": "Test Blocklist",
                        "pending": 1,
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "data": {"type": "exact", "urls": []},
                        "id": 123,
                        "name": "Test Blocklist",
                        "pending": 0,
                    },
                },
            ],
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/replace",
            status_code=200,
            json={
                "data": {"type": "exact", "urls": []},
                "id": 123,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Edited",
                "name": "Test Blocklist",
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

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.test.com"],
        }

        result = remove_action.run(arguments)

        assert result["action_name"] == "remove_from_blocklist"
        assert result["action_response"]["modify_type"] == "Edited"
        assert (
            "Successfully removed from blocklist Test Blocklist (id = 123): 1/1 removed (0 already missing)"
            in result["action_status"]
        )


def test_remove_from_blocklist_noop_when_items_are_absent(remove_action):
    """Test remove returns no-op when requested items are not in blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={
                "id": 123,
                "name": "Test Blocklist",
                "data": {"type": "exact", "urls": ["www.present.com"]},
            },
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.absent.com", "www.absent.com"],
        }

        result = remove_action.run(arguments)

        assert (
            "No item(s) removed from blocklist Test Blocklist (id = 123): 0/2 removed (2 already missing)"
            in result["action_status"]
        )
        assert len(mock_requests.request_history) == 1
