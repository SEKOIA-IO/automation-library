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
                "data": {
                    "type": "exact",
                    "urls": ["new-blocked.com", "another-blocked.com"],
                },
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
                    "data": {
                        "type": "exact",
                        "urls": ["new-blocked.com", "another-blocked.com"],
                    },
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
            "api_token": "fake_api_token",
            "blocklist_id": "456",
            "items": ["new-blocked.com", "another-blocked.com", "new-blocked.com"],
            "blocklist_type": "exact",
        }

        result = replace_action.run(arguments)
        replace_request_body = mock_requests.request_history[0].json()

        assert result is None
        replace_action.log.assert_any_call(
            level="info",
            message="Successfully replaced blocklist Updated Blocklist (id = 456) with 2 item(s)",
        )
        assert replace_request_body == {
            "data": {
                "type": "exact",
                "urls": ["another-blocked.com", "new-blocked.com"],
            }
        }


def test_replace_blocklist_missing_required_params(replace_action):
    """Test that replace action fails when required parameters are missing"""
    arguments = {
        "api_token": "fake_api_token",
        "items": ["new-blocked.com"],
    }

    with pytest.raises(ValidationError):
        # Missing field 'blocklist_id' should cause validation error
        replace_action.run(arguments)


def test_replace_blocklist_should_not_sort_when_sort_items_false(replace_action):
    """Test replace preserves insertion order when sort_items is false"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/456/replace",
            status_code=200,
            json={"id": 456, "name": "Updated Blocklist", "pending": 1},
        )

        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[{"id": 456, "pending": 0}],
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "456",
            "items": ["www.z.com", "www.a.com", "www.z.com"],
            "sort_items": False,
        }

        replace_action.run(arguments)

        replace_request_body = mock_requests.request_history[0].json()
        assert replace_request_body == {"data": {"type": "exact", "urls": ["www.z.com", "www.a.com"]}}
