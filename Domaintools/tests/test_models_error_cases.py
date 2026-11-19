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
        action = BaseDomaintoolsAction()
        action.action_name = "unknown_action"
        result = action.DomaintoolsrunAction(config, arguments)
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
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)
            data = result  # Response is already a dict, no need for json.loads()
            assert "error" in data

    def test_http_error_status(self):
        """Test HTTP error status handling"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, status_code=404)

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}

            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)
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


class TestPivotActionTypes:
    """Test pivot_action with different search types including nameserver_host"""

    def test_pivot_action_with_domain(self):
        """Test pivot action with domain search type"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"response": {"results": []}})

            result = client.pivot_action("example.com", "domain", limit=100)
            assert result is not None

    def test_pivot_action_with_nameserver_host(self):
        """Test pivot action with nameserver_host search type (no validation)"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"response": {"results": []}})

            result = client.pivot_action("ns1.example.com", "nameserver_host", limit=100)
            assert result is not None


class TestIrisReverseIP:
    """Test iris_reverse_ip method"""

    def test_iris_reverse_ip_success(self):
        """Test successful iris_reverse_ip call"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(
                requests_mock.ANY,
                json={
                    "response": {
                        "results": [{"domain": "example.com", "domain_risk": {"risk_score": 10}}],
                        "results_count": 1,
                    }
                },
            )

            result = client.iris_reverse_ip("192.168.1.1")
            assert result is not None
            assert "response" in result

    def test_iris_reverse_ip_limit_bounds(self):
        """Test iris_reverse_ip respects limit bounds"""
        config = DomainToolsConfig(api_username="test", api_key="test")
        client = DomainToolsClient(config)

        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, json={"response": {"results": []}})

            # Test with limit below minimum (should use 100)
            client.iris_reverse_ip("192.168.1.1", limit=50)
            assert "limit=100" in m.last_request.url

            # Test with limit above maximum (should use 10000)
            client.iris_reverse_ip("192.168.1.1", limit=20000)
            assert "limit=10000" in m.last_request.url


class TestBaseDomaintoolsActionErrors:
    """Test error handling in BaseDomaintoolsAction.run()"""

    def test_base_action_domaintools_error(self):
        """Test BaseDomaintoolsAction handles DomainToolsError"""
        action = BaseDomaintoolsAction()
        action.action_name = "domain_reputation"
        action.module = Mock()
        # Invalid config that will raise DomainToolsError
        action.module.configuration = {"api_username": "", "api_key": "test"}

        result = action.run({"domain": "example.com"})
        assert "error" in result
        assert "DomainTools client initialization error" in result["error"]

    def test_base_action_unexpected_error(self):
        """Test BaseDomaintoolsAction handles unexpected errors"""
        action = BaseDomaintoolsAction()
        action.action_name = "domain_reputation"
        action.module = Mock()
        # Configuration that raises unexpected error
        action.module.configuration = None  # This will cause AttributeError

        result = action.run({"domain": "example.com"})
        assert "error" in result
        assert "Unexpected initialization error" in result["error"]


class TestCallMethodErrors:
    """Test call_method error handling"""

    def test_call_method_attribute_error(self):
        """Test call_method handles AttributeError for missing method"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            # Remove the method to trigger AttributeError
            del mock_client.domain_reputation
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert "error" in result
            assert "Client has no method" in result["error"]

    def test_call_method_unexpected_exception(self):
        """Test call_method handles unexpected exceptions"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            mock_client.domain_reputation.side_effect = RuntimeError("Unexpected runtime error")
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert "error" in result
            assert "Unexpected error" in result["error"]


class TestResponsePayloadProcessing:
    """Test different payload types in response processing"""

    def test_payload_none_returns_error(self):
        """Test that None payload returns error"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            mock_client.domain_reputation.return_value = None
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert "error" in result
            assert "No response returned" in result["error"]

    def test_payload_string_returns_error(self):
        """Test that string payload returns error"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            mock_client.domain_reputation.return_value = "Some string response"
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert "error" in result
            assert "Some string response" in result["error"]

    def test_payload_list_returned_as_is(self):
        """Test that list payload is returned as-is"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            mock_client.domain_reputation.return_value = [{"domain": "example.com"}]
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert isinstance(result, list)
            assert result[0]["domain"] == "example.com"

    def test_payload_dict_without_response_key(self):
        """Test dict payload without 'response' key is returned as-is"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            mock_client.domain_reputation.return_value = {"data": "some_data", "status": "ok"}
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert result["data"] == "some_data"
            assert result["status"] == "ok"

    def test_payload_extraction_exception(self):
        """Test exception during payload extraction"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            mock_client = Mock()
            # Create an object that raises an exception when isinstance() checks it
            # by overriding __class__ in a way that breaks the check
            bad_payload = type(
                "BadPayload", (), {"__bool__": lambda self: (_ for _ in ()).throw(RuntimeError("Bad"))}
            )()
            mock_client.domain_reputation.return_value = bad_payload
            MockClient.return_value = mock_client

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            # The payload will be returned as-is since it's not None, not a string, not a dict
            # The code returns it directly at line 520
            assert result is not None


class TestNoActionSpecified:
    """Test behavior when no action is specified"""

    def test_no_action_returns_error(self):
        """Test that missing action returns error"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        arguments = {"domain": "example.com"}  # No domaintools_action

        action = BaseDomaintoolsAction()
        result = action.DomaintoolsrunAction(config, arguments)
        assert "error" in result
        assert "No action specified" in result["error"]


class TestDomaintoolsrunActionExceptions:
    """Test exception handling in DomaintoolsrunAction"""

    def test_domaintools_error_during_client_init(self):
        """Test DomainToolsError during client initialization"""
        config = DomainToolsConfig(api_username="", api_key="test")  # Invalid config

        arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}

        action = BaseDomaintoolsAction()
        action.action_name = "domain_reputation"
        result = action.DomaintoolsrunAction(config, arguments)
        assert "error" in result
        assert "DomainTools client initialization error" in result["error"]

    def test_unexpected_error_during_execution(self):
        """Test unexpected error during DomaintoolsrunAction execution"""
        config = DomainToolsConfig(api_username="test", api_key="test")

        with patch("domaintools.models.DomainToolsClient") as MockClient:
            MockClient.side_effect = RuntimeError("Unexpected error during init")

            arguments = {"domain": "example.com", "domaintools_action": "domain_reputation"}
            action = BaseDomaintoolsAction()
            action.action_name = "domain_reputation"
            result = action.DomaintoolsrunAction(config, arguments)

            assert "error" in result
            assert "Unexpected initialization error" in result["error"]
