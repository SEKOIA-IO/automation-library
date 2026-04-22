import pytest
import requests_mock
from unittest.mock import MagicMock

from netskope_modules import NetskopeModule
from netskope_modules.actions.add_to_blocklist import AddToBlocklistAction
from netskope_modules.actions.replace_blocklist import ReplaceBlocklistAction


@pytest.fixture
def add_action(symphony_storage):
    module = NetskopeModule()
    action = AddToBlocklistAction(module=module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    action.module.configuration = {
        "base_url": "https://my.fake.netskope.com",
        "api_key": "fake_api_key",
    }
    return action


@pytest.fixture
def replace_action(symphony_storage):
    module = NetskopeModule()
    action = ReplaceBlocklistAction(module=module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    action.module.configuration = {
        "base_url": "https://my.fake.netskope.com",
        "api_key": "fake_api_key",
    }
    return action


def test_add_to_blocklist_success(add_action):
    """Test successful addition of items to blocklist"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the append request
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={
                "data": {
                    "type": "exact",
                    "urls": ["www.test.com", "malicious.com"]
                },
                "id": 123,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Edited",
                "name": "Test Blocklist",
                "pending": 1
            }
        )

        # Mock the deploy request
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[
                {
                    "data": {
                        "type": "exact",
                        "urls": ["www.test.com", "malicious.com"]
                    },
                    "id": 123,
                    "modify_by": "Netskope API",
                    "modify_time": "1997-01-01 00:00:00",
                    "modify_type": "Created",
                    "name": "Test Blocklist",
                    "pending": 0
                }
            ]
        )

        arguments = {
            "url_list_id": "123",
            "items": ["www.test.com", "malicious.com"]
        }

        result = add_action.run(arguments)

        assert result["add_result"]["id"] == 123
        assert result["add_result"]["pending"] == 1
        assert len(result["deploy_result"]) == 1
        assert result["deploy_result"][0]["pending"] == 0
        assert "Successfully added 2 item(s) to blocklist" in result["message"]


def test_add_to_blocklist_api_error(add_action):
    """Test API error handling for add to blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=400,
            json={"error": {"message": "Invalid URL list ID"}}
        )

        arguments = {
            "url_list_id": "123",
            "items": ["www.test.com"]
        }

        with pytest.raises(ValueError, match="Netskope API returned an error: Invalid URL list ID"):
            add_action.run(arguments)


def test_replace_blocklist_success(replace_action):
    """Test successful replacement of blocklist"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the replace request
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/456/replace",
            status_code=200,
            json={
                "data": {
                    "type": "exact",
                    "urls": ["new-blocked.com", "another-blocked.com"]
                },
                "id": 456,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Edited",
                "name": "Updated Blocklist",
                "pending": 1
            }
        )

        # Mock the deploy request
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[
                {
                    "data": {
                        "type": "exact",
                        "urls": ["new-blocked.com", "another-blocked.com"]
                    },
                    "id": 456,
                    "modify_by": "Netskope API",
                    "modify_time": "1997-01-01 00:00:00",
                    "modify_type": "Created",
                    "name": "Updated Blocklist",
                    "pending": 0
                }
            ]
        )

        arguments = {
            "url_list_id": "456",
            "items": ["new-blocked.com", "another-blocked.com"],
            "name": "Updated Blocklist",
            "type": "exact"
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
        # Missing name and type
    }

    with pytest.raises(ValueError, match="name and type are required for replace action"):
        replace_action.run(arguments)


def test_deploy_error_handling(add_action):
    """Test error handling during deploy phase"""
    with requests_mock.Mocker() as mock_requests:
        # Mock successful append
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"id": 123, "pending": 1}
        )

        # Mock deploy failure
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=500,
            json={"error": {"message": "Deploy failed"}}
        )

        arguments = {
            "url_list_id": "123",
            "items": ["www.test.com"]
        }

        with pytest.raises(ValueError, match="Netskope API returned an error: Deploy failed"):
            add_action.run(arguments)
