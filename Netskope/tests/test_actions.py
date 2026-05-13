from unittest.mock import MagicMock

import pytest
import requests.exceptions
import requests_mock
from pydantic import ValidationError

from netskope_modules import NetskopeModule
from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_delete_blocklist import DeleteBlocklistAction
from netskope_modules.actions.action_replace_blocklist import ReplaceBlocklistAction


@pytest.fixture
def append_action(symphony_storage):
    module = NetskopeModule()
    action = AppendToBlocklistAction(module=module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    action.module.configuration = {
        "base_url": "https://my.fake.netskope.com",
        "api_token": "fake_api_token",
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
        "api_token": "fake_api_token",
    }
    return action


@pytest.fixture
def delete_action(symphony_storage):
    module = NetskopeModule()
    action = DeleteBlocklistAction(module=module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    action.module.configuration = {
        "base_url": "https://my.fake.netskope.com",
        "api_token": "fake_api_token",
    }
    return action


def test_append_to_blocklist_success(append_action):
    """Test successful appending of items to blocklist"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the append request
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={
                "data": {"type": "exact", "urls": ["www.test.com", "malicious.com"]},
                "id": 123,
                "modify_by": "Netskope API",
                "modify_time": "1997-01-01 00:00:00",
                "modify_type": "Edited",
                "name": "Test Blocklist",
                "pending": 1,
            },
        )

        # Mock the deploy request
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[
                {
                    "data": {"type": "exact", "urls": ["www.test.com", "malicious.com"]},
                    "id": 123,
                    "modify_by": "Netskope API",
                    "modify_time": "1997-01-01 00:00:00",
                    "modify_type": "Created",
                    "name": "Test Blocklist",
                    "pending": 0,
                }
            ],
        )

        arguments = {"url_list_id": "123", "items": ["www.test.com", "malicious.com"]}

        result = append_action.run(arguments)

        assert result["append_result"]["id"] == 123
        assert result["append_result"]["pending"] == 1
        assert len(result["deploy_result"]) == 1
        assert result["deploy_result"][0]["pending"] == 0
        assert "Successfully appended 2 item(s) to blocklist" in result["message"]


def test_append_to_blocklist_api_error(append_action):
    """Test API error handling for append to blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=400,
            json={"error": {"message": "Invalid URL list ID"}},
        )

        arguments = {"url_list_id": "123", "items": ["www.test.com"]}

        with pytest.raises(requests.exceptions.HTTPError):
            append_action.run(arguments)


def test_replace_blocklist_success(replace_action):
    """Test successful replacement of blocklist"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the replace request
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

        # Mock the deploy request
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


def test_replace_blocklist_missing_required_params(replace_action):
    """Test that replace action fails when required parameters are missing"""
    arguments = {
        "url_list_id": "456",
        "items": ["new-blocked.com"],
        # Missing name and type
    }

    with pytest.raises(ValidationError):
        # Missing field 'name' should cause validation error
        replace_action.run(arguments)


def test_deploy_error_handling(append_action):
    """Test error handling during deploy phase"""
    with requests_mock.Mocker() as mock_requests:
        # Mock successful append
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"id": 123, "pending": 1},
        )

        # Mock deploy failure
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=500,
            json={"error": {"message": "Deploy failed"}},
        )

        arguments = {"url_list_id": "123", "items": ["www.test.com"]}

        with pytest.raises(requests.exceptions.HTTPError):
            append_action.run(arguments)


def test_api_error_in_json_response(append_action):
    """Test handling of error message in JSON response with 200 status"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the append request with 200 status but error in JSON
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"error": {"message": "Invalid URL format"}},
        )

        arguments = {"url_list_id": "123", "items": ["invalid-url"]}

        with pytest.raises(ValueError, match="Netskope API returned an error: Invalid URL format"):
            append_action.run(arguments)


def test_invalid_json_response(append_action):
    """Test handling of invalid JSON response with 200 status"""
    with requests_mock.Mocker() as mock_requests:
        # Mock the append request with 200 status but invalid JSON
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            text="<html>Invalid JSON Response</html>",
        )

        arguments = {"url_list_id": "123", "items": ["www.test.com"]}

        # Should raise an error for invalid JSON
        from requests.exceptions import JSONDecodeError

        with pytest.raises(JSONDecodeError):
            append_action.run(arguments)
