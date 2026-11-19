import pytest
from unittest.mock import Mock, patch, PropertyMock, MagicMock
from pymisp import PyMISPError
import requests

from misp.trigger_misp_ids_attributes_to_ioc_collection import (
    MISPIDSAttributesToIOCCollectionTrigger,
)


class TestMISPIDSAttributesToIOCCollectionTrigger:
    """Unit tests for MISP IDS Attributes to IOC Collection trigger."""

    # ------------------------------------------------------------------ #
    # Global test isolation (CRITICAL)
    # ------------------------------------------------------------------ #

    @pytest.fixture(autouse=True)
    def disable_trigger_logging(self, monkeypatch):
        """
        Disable Sekoia Trigger HTTP logging.
        Trigger.log() internally sends HTTP requests, which must never happen
        during unit tests.
        """
        monkeypatch.setattr(
            "sekoia_automation.trigger.Trigger._send_logs_to_api",
            lambda self: None,
        )

    @pytest.fixture
    def trigger(self):
        mock_module = Mock()
        mock_module.configuration = {
            "misp_url": "https://misp.example.com",
            "misp_api_key": "test_misp_api_key",
            "sekoia_api_key": "test_sekoia_api_key",
        }

        trigger = MISPIDSAttributesToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {
            "ioc_collection_server": "https://api.sekoia.io",
            "ioc_collection_uuid": "test-collection-uuid",
            "lookback_days": "1",
            "sleep_time": "300",
        }

        trigger._logger = Mock()
        trigger.log = Mock()  # prevent Trigger.log() side effects
        return trigger

    @pytest.fixture
    def mock_session(self, trigger):
        """Fixture that injects a mock HTTP session into the trigger and prevents initialize_http_session from replacing it."""
        session = MagicMock()
        trigger.http_session = session
        trigger.initialize_http_session = Mock()
        return session

    # ------------------------------------------------------------------ #
    # Configuration properties
    # ------------------------------------------------------------------ #

    def test_sleep_time_default(self, trigger):
        trigger.configuration = {}
        assert trigger.sleep_time == 300

    def test_sleep_time_custom(self, trigger):
        trigger.configuration = {"sleep_time": "600"}
        assert trigger.sleep_time == 600

    def test_lookback_days_default(self, trigger):
        trigger.configuration = {}
        assert trigger.lookback_days == "1"

    def test_ioc_collection_server(self, trigger):
        assert trigger.ioc_collection_server == "https://api.sekoia.io"

    def test_ioc_collection_uuid(self, trigger):
        assert trigger.ioc_collection_uuid == "test-collection-uuid"

    # def test_sekoia_api_key(self, trigger):
    #    assert trigger.sekoia_api_key == "test_sekoia_api_key"

    # ------------------------------------------------------------------ #
    # Proxy configuration
    # ------------------------------------------------------------------ #

    def test_proxies_from_module_configuration(self, trigger):
        """Test that proxies are retrieved from module configuration."""
        trigger.module.configuration["http_proxy"] = "http://proxy.example.com:8080"
        trigger.module.configuration["https_proxy"] = "https://proxy.example.com:8443"

        proxies = trigger.proxies

        assert proxies == {
            "http": "http://proxy.example.com:8080",
            "https": "https://proxy.example.com:8443",
        }

    def test_proxies_http_only(self, trigger):
        """Test proxies with only HTTP configured."""
        trigger.module.configuration["http_proxy"] = "http://proxy.example.com:8080"

        proxies = trigger.proxies

        assert proxies == {"http": "http://proxy.example.com:8080"}

    def test_proxies_https_only(self, trigger):
        """Test proxies with only HTTPS configured."""
        trigger.module.configuration["https_proxy"] = "https://proxy.example.com:8443"

        proxies = trigger.proxies

        assert proxies == {"https": "https://proxy.example.com:8443"}

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.getproxies")
    def test_proxies_fallback_to_environment(self, mock_getproxies, trigger):
        """Test that proxies fall back to environment variables when not configured."""
        mock_getproxies.return_value = {
            "http": "http://env-proxy.example.com:8080",
            "https": "https://env-proxy.example.com:8443",
        }

        proxies = trigger.proxies

        assert proxies == {
            "http": "http://env-proxy.example.com:8080",
            "https": "https://env-proxy.example.com:8443",
        }
        mock_getproxies.assert_called_once()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.getproxies")
    def test_proxies_module_config_takes_priority(self, mock_getproxies, trigger):
        """Test that module configuration takes priority over environment variables."""
        trigger.module.configuration["http_proxy"] = "http://config-proxy.example.com:8080"
        trigger.module.configuration["https_proxy"] = "https://config-proxy.example.com:8443"
        mock_getproxies.return_value = {
            "http": "http://env-proxy.example.com:8080",
            "https": "https://env-proxy.example.com:8443",
        }

        proxies = trigger.proxies

        assert proxies == {
            "http": "http://config-proxy.example.com:8080",
            "https": "https://config-proxy.example.com:8443",
        }
        mock_getproxies.assert_not_called()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.getproxies")
    def test_proxies_returns_none_when_no_proxy(self, mock_getproxies, trigger):
        """Test that proxies returns None when no proxy is configured."""
        mock_getproxies.return_value = {}

        proxies = trigger.proxies

        assert proxies is None

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.getproxies")
    def test_proxies_environment_with_no_proxy(self, mock_getproxies, trigger):
        """Test proxies from environment including NO_PROXY.

        urllib.request.getproxies() returns 'no' but requests expects 'no_proxy'.
        """
        mock_getproxies.return_value = {
            "http": "http://env-proxy.example.com:8080",
            "https": "https://env-proxy.example.com:8443",
            "no": "localhost,127.0.0.1",
        }

        proxies = trigger.proxies

        assert proxies == {
            "http": "http://env-proxy.example.com:8080",
            "https": "https://env-proxy.example.com:8443",
            "no_proxy": "localhost,127.0.0.1",
        }

    # ------------------------------------------------------------------ #
    # HTTP session initialization
    # ------------------------------------------------------------------ #

    def test_initialize_http_session_defaults(self, trigger):
        """Test that the HTTP session is configured with secure defaults (trust_env=False, verify=True)."""
        trigger.initialize_http_session()

        assert trigger.http_session is not None
        assert trigger.http_session.trust_env is False
        assert trigger.http_session.verify is True

    def test_initialize_http_session_verify_ssl_disabled(self, trigger):
        """Test that verify_ssl=False disables TLS verification in the session."""
        trigger.configuration["verify_ssl"] = False
        trigger.initialize_http_session()

        assert trigger.http_session is not None
        assert trigger.http_session.verify is False

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_success(self, mock_pymisp, trigger):
        misp = Mock()
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        assert trigger.misp_client == misp
        mock_pymisp.assert_called_once_with(
            url="https://misp.example.com",
            key="test_misp_api_key",
            ssl=True,
            debug=False,
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_with_proxy(self, mock_pymisp, trigger):
        """Test MISP client initialization with proxy configuration."""
        misp = Mock()
        mock_pymisp.return_value = misp
        trigger.module.configuration["http_proxy"] = "http://proxy.example.com:8080"
        trigger.module.configuration["https_proxy"] = "https://proxy.example.com:8443"

        trigger.initialize_misp_client()

        assert trigger.misp_client == misp
        mock_pymisp.assert_called_once_with(
            url="https://misp.example.com",
            key="test_misp_api_key",
            ssl=True,
            debug=False,
            proxies={
                "http": "http://proxy.example.com:8080",
                "https": "https://proxy.example.com:8443",
            },
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_proxy_credentials_masked_in_logs(self, mock_pymisp, trigger):
        """Test that proxy credentials are masked in logs."""
        misp = Mock()
        mock_pymisp.return_value = misp
        trigger.module.configuration["http_proxy"] = "http://user:password@proxy.example.com:8080"

        trigger.initialize_misp_client()

        # Check that log was called with masked proxy URL
        log_calls = [str(call) for call in trigger.log.call_args_list]
        log_messages = " ".join(log_calls)
        assert "user:password" not in log_messages
        assert "proxy.example.com:8080" in log_messages

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_version_check_success(self, mock_pymisp, trigger):
        """Test successful MISP version check during initialization."""
        misp = Mock()
        misp.misp_instance_version = {"version": "2.4.150"}
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        assert trigger.misp_client == misp

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_version_check_failure(self, mock_pymisp, trigger):
        """Test that initialization continues even if version check fails."""
        misp = Mock()
        type(misp).misp_instance_version = PropertyMock(side_effect=Exception("Version check failed"))
        mock_pymisp.return_value = misp

        # Should not raise, just log a warning
        trigger.initialize_misp_client()

        assert trigger.misp_client == misp

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_proxy_error(self, mock_pymisp, trigger):
        """Test ProxyError during MISP client initialization."""
        mock_pymisp.side_effect = requests.exceptions.ProxyError("Proxy connection failed")

        with pytest.raises(requests.exceptions.ProxyError):
            trigger.initialize_misp_client()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_connection_error(self, mock_pymisp, trigger):
        """Test ConnectionError during MISP client initialization."""
        mock_pymisp.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            trigger.initialize_misp_client()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_timeout_error(self, mock_pymisp, trigger):
        """Test Timeout during MISP client initialization."""
        mock_pymisp.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(requests.exceptions.Timeout):
            trigger.initialize_misp_client()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_ssl_error(self, mock_pymisp, trigger):
        """Test SSLError during MISP client initialization."""
        mock_pymisp.side_effect = requests.exceptions.SSLError("SSL certificate verify failed")

        with pytest.raises(requests.exceptions.SSLError):
            trigger.initialize_misp_client()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_pymisp_error(self, mock_pymisp, trigger):
        """Test PyMISPError during MISP client initialization."""
        mock_pymisp.side_effect = PyMISPError("Invalid API key")

        with pytest.raises(PyMISPError):
            trigger.initialize_misp_client()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_error(self, mock_pymisp, trigger):
        mock_pymisp.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            trigger.initialize_misp_client()

    def test_initialize_cache_success(self, trigger):
        trigger.configuration["lookback_days"] = "7"
        trigger.initialize_cache()

        assert trigger.processed_attributes is not None
        assert trigger.processed_attributes.maxsize == 100000
        assert trigger.processed_attributes.ttl == 7 * 24 * 3600

    def test_initialize_cache_error(self, trigger):
        trigger.configuration["lookback_days"] = "invalid"

        with pytest.raises(Exception):
            trigger.initialize_cache()

    # ------------------------------------------------------------------ #
    # Filtering & extraction
    # ------------------------------------------------------------------ #

    def test_filter_supported_types(self, trigger):
        attrs = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="example.com", uuid="2"),
            Mock(type="email-src", value="a@b.c", uuid="3"),
            Mock(type="sha256", value="a" * 64, uuid="4"),
            Mock(type="mutex", value="x", uuid="5"),
        ]

        filtered = trigger.filter_supported_types(attrs)

        assert [a.type for a in filtered] == ["ip-dst", "domain", "sha256"]

    def test_extract_ioc_value_simple(self, trigger):
        assert trigger.extract_ioc_value(Mock(type="ip-dst", value="1.1.1.1")) == "1.1.1.1"
        assert trigger.extract_ioc_value(Mock(type="domain", value="example.com")) == "example.com"
        assert trigger.extract_ioc_value(Mock(type="sha256", value="a" * 64)) == "a" * 64
        assert trigger.extract_ioc_value(Mock(type="url", value="https://evil.com/x")) == "https://evil.com/x"

    def test_extract_ioc_value_composite(self, trigger):
        sha256 = "a" * 64
        assert trigger.extract_ioc_value(Mock(type="filename|sha256", value=f"x.exe|{sha256}")) == sha256
        assert trigger.extract_ioc_value(Mock(type="filename|md5", value="x.exe|abc123")) == "abc123"
        assert trigger.extract_ioc_value(Mock(type="filename|sha1", value="x.exe|def456")) == "def456"
        assert trigger.extract_ioc_value(Mock(type="ip-dst|port", value="1.1.1.1|443")) == "1.1.1.1"
        assert trigger.extract_ioc_value(Mock(type="domain|ip", value="example.com|1.1.1.1")) == "example.com"

    def test_extract_ioc_value_ip_port_colon_separator(self, trigger):
        """Some MISP instances use ':' instead of '|' for ip-dst|port values."""
        assert trigger.extract_ioc_value(Mock(type="ip-dst|port", value="1.2.3.4:8080")) == "1.2.3.4"

    def test_extract_ioc_value_filename_hash_no_separator(self, trigger):
        """Malformed filename|hash with no separator returns raw value (will fail validation)."""
        assert trigger.extract_ioc_value(Mock(type="filename|sha256", value="malformed")) == "malformed"

    def test_extract_ioc_value_domain_ip_no_separator(self, trigger):
        """domain|ip with no separator returns raw value (will fail validation)."""
        assert trigger.extract_ioc_value(Mock(type="domain|ip", value="example.com")) == "example.com"

    def test_extract_ioc_value_unknown_type(self, trigger):
        attr = Mock(type="unknown-type", value="whatever")
        assert trigger.extract_ioc_value(attr) == "whatever"

    # ------------------------------------------------------------------ #
    # IOC validation
    # ------------------------------------------------------------------ #

    def test_validate_ioc_ipv4_valid(self, trigger):
        assert trigger.validate_ioc_value("1.2.3.4", "ip-dst") is True
        assert trigger.validate_ioc_value("255.255.255.255", "ip-dst") is True
        assert trigger.validate_ioc_value("0.0.0.0", "ip-dst") is True

    def test_validate_ioc_ipv4_invalid(self, trigger):
        assert trigger.validate_ioc_value("999.1.1.1", "ip-dst") is False
        assert trigger.validate_ioc_value("1.2.3", "ip-dst") is False
        assert trigger.validate_ioc_value("not-an-ip", "ip-dst") is False
        assert trigger.validate_ioc_value("1.2.3.4.5", "ip-dst") is False

    def test_validate_ioc_ipv6_valid(self, trigger):
        """IPv6 addresses must be accepted for ip-dst and ip-dst|port."""
        assert trigger.validate_ioc_value("2001:db8::1", "ip-dst") is True
        assert trigger.validate_ioc_value("::1", "ip-dst") is True
        assert trigger.validate_ioc_value("fe80::1", "ip-dst") is True
        assert trigger.validate_ioc_value("2001:0db8:0000:0000:0000:0000:0000:0001", "ip-dst") is True
        assert trigger.validate_ioc_value("2001:db8::1", "ip-dst|port") is True

    def test_validate_ioc_ipv6_invalid(self, trigger):
        """Malformed IPv6 must be rejected."""
        assert trigger.validate_ioc_value("gggg::1", "ip-dst") is False
        assert trigger.validate_ioc_value("1.2.3.4:80", "ip-dst") is False  # ip:port not a bare IP

    def test_validate_ioc_ip_port_with_colon_rejected(self, trigger):
        """After extraction the validated value must be a bare IP, not ip:port."""
        # '1.2.3.4:80' is not a valid bare IPv4 — extraction should strip the port first
        assert trigger.validate_ioc_value("1.2.3.4:80", "ip-dst|port") is False
        # But the extracted IP alone must pass
        assert trigger.validate_ioc_value("1.2.3.4", "ip-dst|port") is True

    def test_validate_ioc_domain_valid(self, trigger):
        assert trigger.validate_ioc_value("example.com", "domain") is True
        assert trigger.validate_ioc_value("sub.example.co.uk", "domain") is True
        assert trigger.validate_ioc_value("evil-domain.org", "domain") is True

    def test_validate_ioc_domain_rejects_ip(self, trigger):
        """An IPv4 address must not pass domain validation."""
        assert trigger.validate_ioc_value("1.2.3.4", "domain") is False
        assert trigger.validate_ioc_value("192.168.1.100", "domain") is False

    def test_validate_ioc_domain_invalid(self, trigger):
        assert trigger.validate_ioc_value("notadomain", "domain") is False
        assert trigger.validate_ioc_value("has space.com", "domain") is False
        assert trigger.validate_ioc_value("", "domain") is False

    def test_validate_ioc_url_valid(self, trigger):
        assert trigger.validate_ioc_value("http://evil.com/path", "url") is True
        assert trigger.validate_ioc_value("https://evil.com/path?q=1", "url") is True
        assert trigger.validate_ioc_value("https://1.2.3.4/malware", "url") is True

    def test_validate_ioc_url_invalid(self, trigger):
        assert trigger.validate_ioc_value("ftp://evil.com", "url") is False
        assert trigger.validate_ioc_value("evil.com/path", "url") is False
        assert trigger.validate_ioc_value("not a url", "url") is False
        assert trigger.validate_ioc_value("https://", "url") is False  # no host

    def test_validate_ioc_md5_valid(self, trigger):
        assert trigger.validate_ioc_value("a" * 32, "md5") is True
        assert trigger.validate_ioc_value("d41d8cd98f00b204e9800998ecf8427e", "md5") is True

    def test_validate_ioc_md5_invalid(self, trigger):
        assert trigger.validate_ioc_value("a" * 31, "md5") is False
        assert trigger.validate_ioc_value("a" * 33, "md5") is False
        assert trigger.validate_ioc_value("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", "md5") is False

    def test_validate_ioc_sha1_valid(self, trigger):
        assert trigger.validate_ioc_value("a" * 40, "sha1") is True

    def test_validate_ioc_sha1_invalid(self, trigger):
        assert trigger.validate_ioc_value("a" * 39, "sha1") is False
        assert trigger.validate_ioc_value("a" * 41, "sha1") is False

    def test_validate_ioc_sha256_valid(self, trigger):
        assert trigger.validate_ioc_value("a" * 64, "sha256") is True

    def test_validate_ioc_sha256_invalid(self, trigger):
        assert trigger.validate_ioc_value("a" * 63, "sha256") is False
        assert trigger.validate_ioc_value("a" * 65, "sha256") is False

    def test_validate_ioc_unknown_type_always_valid(self, trigger):
        """Unknown types pass through without validation."""
        assert trigger.validate_ioc_value("whatever", "unknown-type") is True

    def test_validate_ioc_composite_types(self, trigger):
        """Composite types use the extracted value's validator."""
        assert trigger.validate_ioc_value("1.2.3.4", "ip-dst|port") is True
        assert trigger.validate_ioc_value("example.com", "domain|ip") is True
        assert trigger.validate_ioc_value("a" * 64, "filename|sha256") is True
        assert trigger.validate_ioc_value("not-an-ip", "ip-dst|port") is False

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_invalid_ioc_skipped_in_run_loop(self, mock_sleep, mock_pymisp, trigger, mock_session):
        """Test that invalid IOC values are skipped with a warning log and not pushed."""
        misp = Mock()
        misp.search.return_value = [
            Mock(type="ip-dst", value="1.2.3.4", uuid="uuid-valid"),
            Mock(type="ip-dst", value="not-an-ip", uuid="uuid-invalid"),
        ]
        mock_pymisp.return_value = misp

        resp = Mock(status_code=202)
        resp.json.return_value = {"task_id": "abc-123"}
        mock_session.post.return_value = resp
        trigger.send_event = Mock()

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, False]
            trigger.run()

        # Only valid IP should have been pushed
        payload = mock_session.post.call_args.kwargs["json"]
        assert "1.2.3.4" in payload["indicators"]
        assert "not-an-ip" not in payload["indicators"]

        # A single warning log should summarize all invalid values
        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("Skipping" in call and "not-an-ip" in call for call in log_calls)

        # send_event should report 1 skipped
        trigger.send_event.assert_called_once_with(
            event_name="MISP IOCs pushed",
            event={
                "iocs_submitted": 1,
                "iocs_skipped_invalid": 1,
                "attributes_processed": 2,
            },
        )

    # ------------------------------------------------------------------ #
    # MISP
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_success(self, mock_pymisp, trigger):
        misp = Mock()
        mock_pymisp.return_value = misp

        misp.search.return_value = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="evil.com", uuid="2"),
        ]

        trigger.initialize_misp_client()
        attrs = trigger.fetch_attributes("1")

        assert len(attrs) == 2
        misp.search.assert_called_once_with(
            controller="attributes",
            to_ids=1,
            pythonify=True,
            publish_timestamp="1d",
            timestamp="1d",
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_pymisp_error(self, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = PyMISPError("boom")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(PyMISPError):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_generic_error(self, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = Exception("Network error")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(Exception, match="Network error"):
            trigger.fetch_attributes("1")

    def test_fetch_attributes_client_not_initialized(self, trigger):
        """Test fetch_attributes raises error when MISP client is None."""
        trigger.misp_client = None

        with pytest.raises(RuntimeError, match="MISP client not initialized"):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_proxy_error(self, mock_pymisp, trigger):
        """Test ProxyError during fetch_attributes."""
        misp = Mock()
        misp.search.side_effect = requests.exceptions.ProxyError("Proxy connection failed")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(requests.exceptions.ProxyError):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_connection_error(self, mock_pymisp, trigger):
        """Test ConnectionError during fetch_attributes."""
        misp = Mock()
        misp.search.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(requests.exceptions.ConnectionError):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_timeout_error(self, mock_pymisp, trigger):
        """Test Timeout during fetch_attributes."""
        misp = Mock()
        misp.search.side_effect = requests.exceptions.Timeout("Request timed out")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(requests.exceptions.Timeout):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_non_list_result(self, mock_pymisp, trigger):
        """Test fetch_attributes when MISP returns non-list result."""
        misp = Mock()
        misp.search.return_value = {"error": "Something went wrong"}
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()
        attrs = trigger.fetch_attributes("1")

        assert attrs == []

    # ------------------------------------------------------------------ #
    # Sekoia push
    # ------------------------------------------------------------------ #

    def test_push_to_sekoia_empty(self, trigger):
        """Test that empty list doesn't make any requests and returns 0."""
        result = trigger.push_to_sekoia([])
        assert result == 0
        trigger.log.assert_called()

    def test_push_to_sekoia_no_session(self, trigger):
        """Test that push_to_sekoia raises RuntimeError when http_session is not initialized."""
        trigger.http_session = None
        with pytest.raises(RuntimeError, match="HTTP session not initialized"):
            trigger.push_to_sekoia(["1.1.1.1"])

    def test_push_to_sekoia_missing_api_key(self, trigger):
        """Test push_to_sekoia returns 0 when sekoia_api_key is missing."""
        trigger.module.configuration["sekoia_api_key"] = ""

        result = trigger.push_to_sekoia(["1.1.1.1", "evil.com"])

        assert result == 0
        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("sekoia_api_key is not configured" in call for call in log_calls)

    def test_push_to_sekoia_missing_ioc_collection_uuid(self, trigger):
        """Test push_to_sekoia returns 0 when ioc_collection_uuid is missing."""
        trigger.configuration["ioc_collection_uuid"] = ""

        result = trigger.push_to_sekoia(["1.1.1.1", "evil.com"])

        assert result == 0
        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("ioc_collection_uuid is not configured" in call for call in log_calls)

    def test_push_to_sekoia_success_202(self, trigger, mock_session):
        """API returns 202 (async) — submitted count equals number of IOCs sent."""
        resp = Mock(status_code=202)
        resp.json.return_value = {"task_id": "abc-123"}
        mock_session.post.return_value = resp

        result = trigger.push_to_sekoia(["1.1.1.1", "evil.com"])

        assert result == 2
        payload = mock_session.post.call_args.kwargs["json"]
        assert payload["format"] == "one_per_line"
        assert "1.1.1.1" in payload["indicators"]

    def test_push_to_sekoia_success_200(self, trigger, mock_session):
        """API returns 200 (sync fallback) — submitted count equals number of IOCs sent."""
        resp = Mock(status_code=200)
        resp.json.return_value = {"task_id": "abc-123"}
        mock_session.post.return_value = resp

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert result == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_with_retry_after(self, mock_sleep, trigger, mock_session):
        r429 = Mock(status_code=429, headers={"Retry-After": "2"})
        r202 = Mock(status_code=202)
        r202.json.return_value = {"task_id": "abc-123"}

        mock_session.post.side_effect = [r429, r202]

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once_with(2)
        assert result == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_without_retry_after(self, mock_sleep, trigger, mock_session):
        r429 = Mock(status_code=429, headers={})
        r202 = Mock(status_code=202)
        r202.json.return_value = {"task_id": "abc-123"}

        mock_session.post.side_effect = [r429, r202]

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 2
        # Should use exponential backoff: 2^0 * 10 = 10
        mock_sleep.assert_called_once_with(10)
        assert result == 1

    def test_push_to_sekoia_auth_error_401(self, trigger, mock_session):
        resp = Mock(status_code=401, text="Unauthorized")
        mock_session.post.return_value = resp

        with pytest.raises(Exception, match="authentication error"):
            trigger.push_to_sekoia(["1.1.1.1"])

    def test_push_to_sekoia_auth_error_403(self, trigger, mock_session):
        resp = Mock(status_code=403, text="Forbidden")
        mock_session.post.return_value = resp

        with pytest.raises(Exception, match="authentication error"):
            trigger.push_to_sekoia(["1.1.1.1"])

    def test_push_to_sekoia_not_found_404(self, trigger, mock_session):
        resp = Mock(status_code=404, text="Not Found")
        mock_session.post.return_value = resp

        with pytest.raises(Exception, match="IOC Collection not found"):
            trigger.push_to_sekoia(["1.1.1.1"])

    def test_push_to_sekoia_client_error_400(self, trigger, mock_session):
        """Test that 400 Bad Request is treated as fatal (non-retriable)."""
        resp = Mock(status_code=400, text="Bad Request")
        mock_session.post.return_value = resp

        with pytest.raises(Exception, match="client error"):
            trigger.push_to_sekoia(["1.1.1.1"])

        # Should only call once, not retry
        assert mock_session.post.call_count == 1

    def test_push_to_sekoia_client_error_422(self, trigger, mock_session):
        """Test that 422 Unprocessable Entity is treated as fatal (non-retriable)."""
        resp = Mock(status_code=422, text="Unprocessable Entity")
        mock_session.post.return_value = resp

        with pytest.raises(Exception, match="client error"):
            trigger.push_to_sekoia(["1.1.1.1"])

        # Should only call once, not retry
        assert mock_session.post.call_count == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_server_error_retry(self, mock_sleep, trigger, mock_session):
        r500 = Mock(status_code=500, text="Server Error")
        r202 = Mock(status_code=202)
        r202.json.return_value = {"task_id": "abc-123"}

        mock_session.post.side_effect = [r500, r202]

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_with(5)
        assert result == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_timeout(self, mock_sleep, trigger, mock_session):
        r202 = Mock(status_code=202)
        r202.json.return_value = {"task_id": "abc-123"}
        mock_session.post.side_effect = [requests.exceptions.Timeout("Timeout"), r202]

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_with(5)
        assert result == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_request_exception(self, mock_sleep, trigger, mock_session):
        r202 = Mock(status_code=202)
        r202.json.return_value = {"task_id": "abc-123"}
        mock_session.post.side_effect = [
            requests.exceptions.RequestException("Connection error"),
            r202,
        ]

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_with(5)
        assert result == 1

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_max_retries_exceeded(self, mock_sleep, trigger, mock_session):
        """When all retries fail, submitted count is 0 for that batch."""
        resp = Mock(status_code=500, text="Server Error")
        mock_session.post.return_value = resp

        result = trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_session.post.call_count == 3  # max_retries
        assert result == 0
        trigger.log.assert_called()

    def test_push_to_sekoia_multiple_batches(self, trigger, mock_session):
        """Test push_to_sekoia correctly batches IOCs into chunks of 100 and returns total submitted."""
        resp = Mock(status_code=202)
        resp.json.return_value = {"task_id": "abc-123"}
        mock_session.post.return_value = resp

        # Create 250 IOCs to trigger 3 batches (100 + 100 + 50)
        ioc_values = [f"1.1.1.{i % 256}" for i in range(250)]

        result = trigger.push_to_sekoia(ioc_values)

        assert mock_session.post.call_count == 3
        assert result == 250

    # ------------------------------------------------------------------ #
    # Run loop
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_main_loop(self, mock_sleep, mock_pymisp, trigger, mock_session):
        misp = Mock()
        misp.search.return_value = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="evil.com", uuid="2"),
        ]
        mock_pymisp.return_value = misp
        trigger.send_event = Mock()

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, False]

            resp = Mock(status_code=202)
            resp.json.return_value = {"task_id": "abc-123"}
            mock_session.post.return_value = resp

            trigger.run()

        assert misp.search.called
        assert mock_session.post.called
        trigger.send_event.assert_called_once_with(
            event_name="MISP IOCs pushed",
            event={
                "iocs_submitted": 2,
                "iocs_skipped_invalid": 0,
                "attributes_processed": 2,
            },
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_no_new_iocs(self, mock_sleep, mock_pymisp, trigger):
        """Test when no new IOCs are found."""
        misp = Mock()
        misp.search.return_value = []
        mock_pymisp.return_value = misp

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, False]

            trigger.run()

        assert misp.search.called

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_with_error_recovery(self, mock_sleep, mock_pymisp, trigger, mock_session):
        misp = Mock()
        misp.search.side_effect = [
            PyMISPError("temp"),
            [Mock(type="ip-dst", value="1.1.1.1", uuid="1")],
        ]
        mock_pymisp.return_value = misp
        trigger.send_event = Mock()

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, True, False]

            resp = Mock(status_code=202)
            resp.json.return_value = {"task_id": "abc-123"}
            mock_session.post.return_value = resp

            trigger.run()

        assert misp.search.call_count == 2
        assert 60 in [c.args[0] for c in mock_sleep.call_args_list]

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_keyboard_interrupt(self, mock_sleep, mock_pymisp, trigger):
        """Test graceful handling of KeyboardInterrupt."""
        misp = Mock()
        misp.search.side_effect = KeyboardInterrupt()
        mock_pymisp.return_value = misp

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.return_value = True

            trigger.run()

        trigger.log.assert_called()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_run_initialization_failure(self, mock_pymisp, trigger):
        mock_pymisp.side_effect = Exception("init failed")
        trigger.run()
        trigger.log.assert_called()

    def test_run_missing_sekoia_api_key(self, trigger):
        """Test run() exits early when sekoia_api_key is missing."""
        trigger.module.configuration["sekoia_api_key"] = ""

        trigger.run()

        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("sekoia_api_key" in call for call in log_calls)

    def test_run_missing_ioc_collection_uuid(self, trigger):
        """Test run() exits early when ioc_collection_uuid is missing."""
        trigger.configuration["ioc_collection_uuid"] = ""

        trigger.run()

        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("ioc_collection_uuid" in call for call in log_calls)

    def test_run_missing_misp_url(self, trigger):
        """Test run() exits early when misp_url is missing."""
        trigger.module.configuration["misp_url"] = ""

        trigger.run()

        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("misp_url" in call for call in log_calls)

    def test_run_missing_misp_api_key(self, trigger):
        """Test run() exits early when misp_api_key is missing."""
        trigger.module.configuration["misp_api_key"] = ""

        trigger.run()

        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("misp_api_key" in call for call in log_calls)

    def test_run_missing_multiple_params(self, trigger):
        """Test run() reports all missing parameters."""
        trigger.module.configuration["sekoia_api_key"] = ""
        trigger.module.configuration["misp_url"] = ""
        trigger.configuration["ioc_collection_uuid"] = ""

        trigger.run()

        log_calls = [str(call) for call in trigger.log.call_args_list]
        log_messages = " ".join(log_calls)
        assert "sekoia_api_key" in log_messages
        assert "misp_url" in log_messages
        assert "ioc_collection_uuid" in log_messages

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_deduplication(self, mock_sleep, mock_pymisp, trigger, mock_session):
        """Test that already processed attributes are not reprocessed."""
        misp = Mock()
        attr1 = Mock(type="ip-dst", value="1.1.1.1", uuid="uuid-1")
        attr2 = Mock(type="domain", value="evil.com", uuid="uuid-2")
        attr3 = Mock(type="ip-dst", value="2.2.2.2", uuid="uuid-3")

        # First call returns attr1 and attr2, second call returns attr1, attr2, and attr3
        misp.search.side_effect = [
            [attr1, attr2],
            [attr1, attr2, attr3],
        ]
        mock_pymisp.return_value = misp

        trigger.send_event = Mock()

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, True, False]

            resp = Mock(status_code=202)
            resp.json.return_value = {"task_id": "abc-123"}
            mock_session.post.return_value = resp

            trigger.run()

        # First call should push 2 IOCs, second call should only push 1 new IOC
        assert mock_session.post.call_count == 2
        # Verify the second call only includes the new IOC
        second_call_payload = mock_session.post.call_args_list[1].kwargs["json"]
        assert "2.2.2.2" in second_call_payload["indicators"]
        assert "1.1.1.1" not in second_call_payload["indicators"]
        assert "evil.com" not in second_call_payload["indicators"]

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_cache_not_initialized_error(self, mock_sleep, mock_pymisp, trigger):
        """Test run() handles RuntimeError when cache is None."""
        misp = Mock()
        misp.search.return_value = [Mock(type="ip-dst", value="1.1.1.1", uuid="1")]
        mock_pymisp.return_value = misp

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, False]

            # Force cache to be None after initialization
            original_init_cache = trigger.initialize_cache

            def mock_init_cache():
                original_init_cache()
                trigger.processed_attributes = None

            trigger.initialize_cache = mock_init_cache

            trigger.run()

        # Should log error about cache not initialized
        log_calls = [str(call) for call in trigger.log.call_args_list]
        assert any("Cache not initialized" in call for call in log_calls)
