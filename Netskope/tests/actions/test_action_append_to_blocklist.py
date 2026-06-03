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
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            [
                {
                    "status_code": 200,
                    "json": {"id": 123, "name": "Test Blocklist", "data": {"type": "exact", "urls": []}},
                },
                {
                    "status_code": 200,
                    "json": {
                        "id": 123,
                        "name": "Test Blocklist",
                        "data": {"type": "exact", "urls": ["malicious.com", "www.test.com"]},
                    },
                },
            ],
        )

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

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.test.com", "malicious.com"],
        }

        result = append_action.run(arguments)

        assert result["action_name"] == "append_to_blocklist"
        assert result["action_response"]["id"] == 123
        assert (
            "Successfully appended to blocklist Test Blocklist (id = 123): 2/2 added (0 duplicates)"
            in result["action_status"]
        )


def test_append_to_blocklist_api_error(append_action):
    """Test API error handling for append to blocklist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={"id": 123, "data": {"type": "exact", "urls": []}},
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=400,
            json={"error": {"message": "Invalid blocklist ID"}},
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.test.com"],
        }

        with pytest.raises(requests.exceptions.HTTPError):
            append_action.run(arguments)


def test_deploy_error_handling(append_action):
    """Test error handling during deploy phase"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={"id": 123, "data": {"type": "exact", "urls": []}},
        )

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

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.test.com"],
        }

        with pytest.raises(requests.exceptions.HTTPError):
            append_action.run(arguments)


def test_api_error_in_json_response(append_action):
    """Test handling of error message in JSON response with 200 status"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={"id": 123, "data": {"type": "exact", "urls": []}},
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"error": {"message": "Invalid URL format"}},
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["invalid-url"],
        }

        with pytest.raises(ValueError, match="Netskope API returned an error: Invalid URL format"):
            append_action.run(arguments)


def test_invalid_json_response(append_action):
    """Test handling of invalid JSON response with 200 status"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={"id": 123, "data": {"type": "exact", "urls": []}},
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            text="<html>Invalid JSON Response</html>",
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.test.com"],
        }

        from requests.exceptions import JSONDecodeError

        with pytest.raises(JSONDecodeError):
            append_action.run(arguments)


def test_append_to_blocklist_should_skip_existing_and_duplicates(append_action):
    """Test append ignores duplicates and existing entries"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            [
                {
                    "status_code": 200,
                    "json": {
                        "id": 123,
                        "data": {"type": "exact", "urls": ["www.already.com"]},
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "id": 123,
                        "data": {"type": "exact", "urls": ["www.already.com", "www.new.com"]},
                    },
                },
            ],
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"id": 123, "pending": 1},
        )

        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[{"id": 123, "pending": 0}],
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.new.com", "www.already.com", "www.new.com"],
        }

        result = append_action.run(arguments)

        assert "(id = 123): 1/3 added (2 duplicates)" in result["action_status"]
        assert len(mock_requests.request_history) == 3
        append_request_body = mock_requests.request_history[1].json()
        assert append_request_body == {"data": {"type": "exact", "urls": ["www.new.com"]}}


def test_append_to_blocklist_noop_when_all_items_exist(append_action):
    """Test append returns no-op when all values already exist"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={
                "id": 123,
                "data": {"type": "exact", "urls": ["www.exist.com"]},
            },
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.exist.com", "www.exist.com"],
        }

        result = append_action.run(arguments)

        assert "No new item(s) appended" in result["action_status"]
        assert "(id = 123): 0/2 added (2 duplicates)" in result["action_status"]
        assert len(mock_requests.request_history) == 1


def test_append_to_blocklist_should_not_sort_when_sort_items_false(append_action):
    """Test append preserves insertion order when sort_items is false"""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            [
                {"status_code": 200, "json": {"id": 123, "data": {"type": "exact", "urls": []}}},
                {
                    "status_code": 200,
                    "json": {"id": 123, "data": {"type": "exact", "urls": ["www.z.com", "www.a.com"]}},
                },
            ],
        )

        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123/append",
            status_code=200,
            json={"id": 123, "pending": 1},
        )

        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json=[{"id": 123, "pending": 0}],
        )

        arguments = {
            "api_token": "fake_api_token",
            "blocklist_id": "123",
            "items": ["www.z.com", "www.a.com", "www.z.com"],
            "sort_items": False,
        }

        append_action.run(arguments)

        append_request_body = mock_requests.request_history[1].json()
        assert append_request_body == {"data": {"type": "exact", "urls": ["www.z.com", "www.a.com"]}}
