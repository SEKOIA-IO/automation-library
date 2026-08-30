"""Test error cases and edge cases in models.py to improve coverage"""

import pytest
import json
import requests
from unittest.mock import Mock, patch
import requests_mock

from domaintools.models import (
    DomainToolsClient,
    DomainToolsConfig,
    DomainToolsError,
    BaseDomaintoolsAction,
    DomaintoolsrunAction,
)


class TestValidations:
    """Test validation methods"""

    def test_validate_domain_invalid_empty(self):
        """Test domain validation with empty string"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Domain must be a non-empty string"):
            client._validate_domain("")

    def test_validate_domain_invalid_no_dot(self):
        """Test domain validation without dot"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Invalid domain format"):
            client._validate_domain("invaliddomain")

    def test_validate_domain_with_protocol(self):
        """Test domain validation strips protocol"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        result = client._validate_domain("https://example.com/path")
        assert result == "example.com"

    def test_validate_ip_invalid(self):
        """Test IP validation with invalid IP"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Invalid IP address format"):
            client._validate_ip("999.999.999.999")

    def test_validate_ip_valid(self):
        """Test IP validation with valid IP"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        result = client._validate_ip("192.168.1.1")
        assert result == "192.168.1.1"

    def test_validate_email_empty(self):
        """Test email validation with empty string"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Email must be a non-empty string"):
            client._validate_email("")

    def test_validate_email_no_at(self):
        """Test email validation without @ symbol"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Invalid email format"):
            client._validate_email("invalidemail.com")

    def test_validate_email_invalid_format(self):
        """Test email validation with invalid format"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Invalid email format"):
            client._validate_email("test@")

    def test_validate_email_valid(self):
        """Test email validation with valid email"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        result = client._validate_email("test@example.com")
        assert result == "test@example.com"


class TestNetworkErrors:
    """Test network error handling"""

    def test_request_timeout(self):
        """Test timeout error handling"""
        config = DomainToolsConfig(api_username="test", api_key="test", timeout=1)
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, exc=requests.exceptions.Timeout("Connection timeout"))

            with pytest.raises(DomainToolsError, match="Request timeout"):
                client.domain_reputation("example.com")

    def test_request_connection_error(self):
        """Test connection error handling"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, exc=requests.exceptions.ConnectionError("Connection failed"))

            with pytest.raises(DomainToolsError, match="Connection error"):
                client.domain_reputation("example.com")

    def test_request_generic_error(self):
        """Test generic request error handling"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, exc=requests.exceptions.RequestException("Generic error"))

            with pytest.raises(DomainToolsError, match="Request error"):
                client.domain_reputation("example.com")

    def test_json_decode_error(self):
        """Test JSON decode error handling"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, text="Invalid JSON", status_code=200)

            # JSONDecodeError is caught as RequestException in the code
            with pytest.raises(DomainToolsError, match="Request error"):
                client.domain_reputation("example.com")


class TestRetryLogic:
    """Test retry logic for 429 errors"""

    def test_retry_429_success_after_retry(self):
        """Test successful retry after 429"""
        config = DomainToolsConfig(api_username="test", api_key="test", rate_limit_delay=0)
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            # First call returns 429, second call succeeds
            m.get(
                requests_mock.ANY,
                [
                    {"status_code": 429, "headers": {"Retry-After": "0"}},
                    {"status_code": 200, "json": {"response": {"results": []}}},
                ],
            )

            result = client.domain_reputation("example.com")
            assert result is not None
            assert m.call_count == 2

    def test_retry_429_max_retries_exceeded(self):
        """Test 429 error when max retries exceeded"""
        config = DomainToolsConfig(api_username="test", api_key="test", rate_limit_delay=0)
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            # Always return 429
            m.get(requests_mock.ANY, status_code=429, headers={"Retry-After": "0"})

            with pytest.raises(DomainToolsError, match="Rate limit exceeded after 3 retries"):
                client.domain_reputation("example.com")

            # Should try 4 times (initial + 3 retries)
            assert m.call_count == 4


class TestPivotAction:
    """Test pivot_action with different search types"""

    def test_pivot_action_with_email(self):
        """Test pivot action with email search type"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"response": {"results": []}})

            result = client.pivot_action("test@example.com", "email", limit=100)
            assert result is not None

    def test_pivot_action_with_ip(self):
        """Test pivot action with IP search type"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"response": {"results": []}})

            result = client.pivot_action("192.168.1.1", "ip", limit=100)
            assert result is not None

    def test_pivot_action_empty_search_term(self):
        """Test pivot action with empty search term"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with pytest.raises(DomainToolsError, match="Search term cannot be empty"):
            client.pivot_action("", "domain")


class TestDispatchErrors:
    """Test error handling in dispatch logic"""

    def test_unknown_action(self):
        """Test dispatch with unknown action"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        arguments = {"domain": "example.com", "domaintools_action": "unknown_action"}

        result = DomaintoolsrunAction(config, arguments)
        data = result  # Response is already a dict, no need for json.loads()
        assert "error" in data
        assert "Unknown action" in data["error"]

    def test_base_action_without_action_name(self):
        """Test BaseDomaintoolsAction without action_name"""
        action = BaseDomaintoolsAction()
        action.module = Mock()
        action.module.configuration = {"api_username": "test", "api_key": "test"}

        with pytest.raises(NotImplementedError, match="Subclass must define 'action_name'"):
            action.run({"domain": "example.com"})


class TestResponseProcessing:
    """Test response processing edge cases"""

    def test_response_with_error_key(self):
        """Test response processing when response contains error key"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"error": "API error message"})

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}

            result = DomaintoolsrunAction(config, arguments)
            data = result  # Response is already a dict, no need for json.loads()
            assert "error" in data

    def test_http_error_status(self):
        """Test HTTP error status handling"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, status_code=404)

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}

            result = DomaintoolsrunAction(config, arguments)
            data = result  # Response is already a dict, no need for json.loads()
            assert "error" in data


class TestConfigValidation:
    """Test configuration validation"""

    def test_config_without_username(self):
        """Test config validation without username"""
        config = DomainToolsConfig(api_username="", api_key="test")

        with pytest.raises(DomainToolsError, match="API username is required"):
            DomainToolsClient(config)

    def test_config_without_key(self):
        """Test config validation without API key"""
        config = DomainToolsConfig(api_username="test", api_key="")

        with pytest.raises(DomainToolsError, match="API key is required"):
            DomainToolsClient(config)

    def test_config_invalid_host(self):
        """Test config validation with invalid host"""
        config = DomainToolsConfig(api_username="test", api_key="test", host="invalid-host")

        with pytest.raises(DomainToolsError, match="Host must include protocol"):
            DomainToolsClient(config)
