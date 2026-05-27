from unittest.mock import MagicMock

import pytest
import requests.exceptions
import requests_mock

from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction


@pytest.fixture
def append_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_append_to_blocklist_success(append_action):
    """Test successful appending of items to blocklist"""
    with requests_mock.Mocker() as mock_requests:
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


def test_deploy_error_handling(append_action):
    """Test error handling during deploy phase"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"id": 123, "pending": 1},
        )

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
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            text="<html>Invalid JSON Response</html>",
        )

        arguments = {"url_list_id": "123", "items": ["www.test.com"]}

        from requests.exceptions import JSONDecodeError

        with pytest.raises(JSONDecodeError):
            append_action.run(arguments)
