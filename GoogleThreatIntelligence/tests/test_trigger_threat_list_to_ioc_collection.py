"""
Unit tests for GoogleThreatIntelligenceThreatListToIOCCollectionTrigger.
"""

import pytest
import requests
from unittest.mock import Mock, patch

from googlethreatintelligence.triggers.threat_list_to_ioc_collection import (
    GoogleThreatIntelligenceThreatListToIOCCollectionTrigger,
    VirusTotalAPIError,
    QuotaExceededError,
    InvalidAPIKeyError,
    ThreatListNotFoundError,
    QueryValidationError,
    VALID_THREAT_LIST_IDS,
    VALID_IOC_TYPES,
    VALID_HAS_VALUES,
)

VT_USERS_CURRENT_URL = "https://www.virustotal.com/api/v3/users/current"


class TestGoogleThreatIntelligenceThreatListToIOCCollectionTrigger:
    """Unit tests for GoogleThreatIntelligenceThreatListToIOCCollectionTrigger."""

    @pytest.fixture(autouse=True)
    def disable_logging(self, monkeypatch):
        """Disable HTTP logging during tests."""
        monkeypatch.setattr(
            "sekoia_automation.trigger.Trigger._send_logs_to_api",
            lambda self: None,
        )

    @pytest.fixture
    def valid_api_key(self):
        """Return a valid 64-character API key."""
        return "a" * 64

    @pytest.fixture
    def trigger(self, valid_api_key):
        """Create trigger instance with mocked module configuration."""
        mock_module = Mock()
        mock_module.configuration = {
            "api_key": valid_api_key,
        }

        trigger = GoogleThreatIntelligenceThreatListToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {
            "polling_frequency_hours": 1,
            "threat_list_id": "malware",
            "ioc_types": ["file", "url"],
            "max_iocs": 1000,
        }
        trigger.context = {}
        trigger.log = Mock()
        trigger.send_event = Mock()
        return trigger

    @pytest.fixture
    def initialized_trigger(self, trigger, requests_mock):
        """Create a trigger with initialize_client() already called (connectivity mocked)."""
        requests_mock.get(VT_USERS_CURRENT_URL, json={}, status_code=200)
        trigger.initialize_client()
        return trigger

    @pytest.fixture
    def sample_vt_response(self):
        """Sample VirusTotal API response matching real API structure."""
        return {
            "iocs": [
                {
                    "data": {
                        "type": "file",
                        "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "attributes": {
                            "md5": "d41d8cd98f00b204e9800998ecf8427e",
                            "gti_assessment": {"threat_score": {"value": 75}},
                            "positives": 12,
                            "total_engines": 70,
                        },
                        "relationships": {
                            "malware_families": {
                                "data": [{"attributes": {"name": "Emotet"}}]
                            }
                        },
                    }
                },
                {
                    "data": {
                        "type": "url",
                        "id": "http://malicious.com/payload.exe",
                        "attributes": {
                            "url": "http://malicious.com/payload.exe",
                            "gti_assessment": {"threat_score": {"value": 82}},
                            "positives": 15,
                            "total_engines": 80,
                        },
                    }
                },
            ],
            "meta": {
                "continuation_cursor": "eyJwYWdlIjoyLCJvZmZzZXQiOjEwMDB9",
                "count": 2,
            },
        }

    # =============================================================================
    # Initialization Tests
    # =============================================================================

    def test_initialization(self, trigger):
        """Test trigger initialization with default values."""
        assert trigger.sleep_time == 3600  # 1 hour default
        assert trigger.processed_events is not None
        assert trigger.session is None

    def test_sleep_time_from_polling_frequency(self, trigger):
        """Test sleep_time is derived from polling_frequency_hours."""
        trigger.configuration["polling_frequency_hours"] = 2
        assert trigger.sleep_time == 2 * 3600

    def test_sleep_time_default(self, trigger):
        """Test sleep_time default value when no polling_frequency_hours."""
        trigger.configuration = {}
        assert trigger.sleep_time == 3600

    def test_polling_frequency_hours_clamped(self, trigger):
        """Test polling_frequency_hours is clamped to [1, 24]."""
        trigger.configuration["polling_frequency_hours"] = 0
        assert trigger.polling_frequency_hours == 1
        assert trigger.sleep_time == 1 * 3600

        trigger.configuration["polling_frequency_hours"] = 30
        assert trigger.polling_frequency_hours == 24
        assert trigger.sleep_time == 24 * 3600

    def test_polling_frequency_hours_invalid(self, trigger):
        """Test polling_frequency_hours falls back to default on invalid values."""
        trigger.configuration["polling_frequency_hours"] = ""
        assert trigger.polling_frequency_hours == 1

        trigger.configuration["polling_frequency_hours"] = "invalid"
        assert trigger.polling_frequency_hours == 1

    def test_polling_frequency_hours_none_falls_back_to_default(self, trigger):
        """Test polling_frequency_hours falls back to default when not set."""
        del trigger.configuration["polling_frequency_hours"]
        assert trigger.polling_frequency_hours == 1
        assert trigger.sleep_time == 3600

    def test_checkpoint_cursor_persisted(self, trigger):
        trigger.save_cursor("cursor123")
        assert trigger.load_cursor() == "cursor123"

        trigger.save_cursor(None)
        assert trigger.load_cursor() is None

    def test_api_key_property(self, trigger, valid_api_key):
        """Test api_key property returns module configuration value."""
        assert trigger.api_key == valid_api_key

    def test_threat_list_id_property(self, trigger):
        """Test threat_list_id property."""
        assert trigger.threat_list_id == "malware"

    def test_threat_list_id_default(self, trigger):
        """Test threat_list_id default value."""
        trigger.configuration = {}
        assert trigger.threat_list_id == "malware"

    def test_ioc_types_property_list(self, trigger):
        """Test ioc_types property with list input."""
        trigger.configuration["ioc_types"] = ["file", "domain"]
        assert trigger.ioc_types == ["file", "domain"]

    def test_ioc_types_property_string(self, trigger):
        """Test ioc_types property with comma-separated string."""
        trigger.configuration["ioc_types"] = "file,url,domain"
        assert trigger.ioc_types == ["file", "url", "domain"]

    def test_ioc_types_filters_invalid(self, trigger):
        """Test ioc_types filters out invalid types."""
        trigger.configuration["ioc_types"] = ["file", "invalid", "url"]
        assert trigger.ioc_types == ["file", "url"]

    def test_max_iocs_property(self, trigger):
        """Test max_iocs property."""
        trigger.configuration["max_iocs"] = 2000
        assert trigger.max_iocs == 2000

    def test_max_iocs_capped_at_4000(self, trigger):
        """Test max_iocs is capped at 4000."""
        trigger.configuration["max_iocs"] = 10000
        assert trigger.max_iocs == 4000

    def test_extra_query_params_property(self, trigger):
        """Test extra_query_params property."""
        trigger.configuration["extra_query_params"] = "gti_score:60+"
        assert trigger.extra_query_params == "gti_score:60+"

    def test_ioc_collection_properties_default(self, trigger):
        """Test default IOC collection properties."""
        assert trigger.ioc_collection_server == "https://api.sekoia.io"
        assert trigger.ioc_collection_uuid == ""

    def test_validate_query_skips_empty_parts(self, trigger):
        """Test validate_query ignores empty query parts."""
        assert trigger.validate_query("gti_score:60+ and  and positives:5") is True

    # =============================================================================
    # Client Initialization Tests
    # =============================================================================

    def test_initialize_client_success(self, trigger, requests_mock):
        """Test successful client initialization."""
        requests_mock.get(VT_USERS_CURRENT_URL, json={}, status_code=200)
        trigger.initialize_client()

        assert trigger.session is not None
        assert trigger.session.headers["X-Apikey"] == trigger.api_key
        assert trigger.session.headers["Accept"] == "application/json"
        trigger.log.assert_called()

    def test_initialize_client_missing_api_key(self, trigger):
        """Test client initialization fails without API key."""
        trigger.module.configuration["api_key"] = ""

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "API key is required" in str(exc_info.value)

    def test_initialize_client_invalid_api_key_format(self, trigger):
        """Test client initialization fails with invalid API key format."""
        trigger.module.configuration["api_key"] = "short_key"

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "Invalid VirusTotal API key format" in str(exc_info.value)

    def test_initialize_client_non_hex_api_key(self, trigger):
        """Test client initialization fails with non-hex characters in API key."""
        trigger.module.configuration["api_key"] = "g" * 64  # 'g' is not a hex char

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "Invalid VirusTotal API key format" in str(exc_info.value)

    def test_initialize_client_too_long_api_key(self, trigger):
        """Test client initialization fails with API key longer than 64 chars."""
        trigger.module.configuration["api_key"] = "a" * 65

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "Invalid VirusTotal API key format" in str(exc_info.value)

    def test_initialize_client_connectivity_401(self, trigger, requests_mock):
        """Test client initialization raises on 401 connectivity check."""
        requests_mock.get(VT_USERS_CURRENT_URL, status_code=401)

        with pytest.raises(InvalidAPIKeyError):
            trigger.initialize_client()

    def test_initialize_client_connectivity_403(self, trigger, requests_mock):
        """Test client initialization raises on 403 connectivity check."""
        requests_mock.get(VT_USERS_CURRENT_URL, status_code=403)

        with pytest.raises(InvalidAPIKeyError):
            trigger.initialize_client()

    def test_initialize_client_connectivity_429(self, trigger, requests_mock):
        """Test client initialization proceeds on 429 (rate limit)."""
        requests_mock.get(VT_USERS_CURRENT_URL, status_code=429)

        trigger.initialize_client()

        assert trigger.session is not None

    def test_initialize_client_connectivity_timeout(self, trigger, requests_mock):
        """Test client initialization raises on connection timeout."""
        requests_mock.get(VT_USERS_CURRENT_URL, exc=requests.exceptions.Timeout)

        with pytest.raises(requests.exceptions.Timeout):
            trigger.initialize_client()

    def test_initialize_client_connectivity_error(self, trigger, requests_mock):
        """Test client initialization raises on connection error."""
        requests_mock.get(
            VT_USERS_CURRENT_URL,
            exc=requests.exceptions.ConnectionError("DNS failure"),
        )

        with pytest.raises(requests.exceptions.ConnectionError):
            trigger.initialize_client()

    # =============================================================================
    # Threat List ID Validation Tests
    # =============================================================================

    def test_validate_threat_list_id_valid(self, trigger):
        """Test validation of valid threat list IDs."""
        for list_id in VALID_THREAT_LIST_IDS:
            assert trigger.validate_threat_list_id(list_id) is True

    def test_validate_threat_list_id_invalid(self, trigger):
        """Test validation rejects invalid threat list ID."""
        with pytest.raises(ThreatListNotFoundError) as exc_info:
            trigger.validate_threat_list_id("invalid-list")

        assert "invalid-list" in str(exc_info.value)

    # =============================================================================
    # Query Validation Tests
    # =============================================================================

    def test_validate_query_empty(self, trigger):
        """Test empty query validation."""
        assert trigger.validate_query("") is True
        assert trigger.validate_query(None) is True

    def test_validate_query_gti_score(self, trigger):
        """Test gti_score filter validation."""
        assert trigger.validate_query("gti_score:60+") is True
        assert trigger.validate_query("gti_score:30-") is True
        assert trigger.validate_query("gti_score:75") is True

    def test_validate_query_positives(self, trigger):
        """Test positives filter validation."""
        assert trigger.validate_query("positives:10+") is True
        assert trigger.validate_query("positives:5-") is True

    def test_validate_query_has_filter(self, trigger):
        """Test has: filter validation."""
        for value in VALID_HAS_VALUES:
            assert trigger.validate_query(f"has:{value}") is True

    def test_validate_query_combined(self, trigger):
        """Test combined filter validation with AND operator."""
        query = "gti_score:60+ and positives:10+ and has:malware_families"
        assert trigger.validate_query(query) is True

    def test_validate_query_invalid_gti_score(self, trigger):
        """Test invalid gti_score filter."""
        with pytest.raises(QueryValidationError):
            trigger.validate_query("gti_score:abc")

    def test_validate_query_invalid_positives(self, trigger):
        """Test invalid positives filter."""
        with pytest.raises(QueryValidationError):
            trigger.validate_query("positives:xyz")

    def test_validate_query_invalid_has_value(self, trigger):
        """Test invalid has: filter value."""
        with pytest.raises(QueryValidationError) as exc_info:
            trigger.validate_query("has:invalid_value")

        assert "invalid_value" in str(exc_info.value)

    def test_validate_query_invalid_filter_prefix(self, trigger):
        """Test invalid filter prefix."""
        with pytest.raises(QueryValidationError) as exc_info:
            trigger.validate_query("unknown_filter:value")

        assert "Invalid query filter" in str(exc_info.value)

    # =============================================================================
    # Numeric Filter Validation Tests
    # =============================================================================

    def test_validate_numeric_filter_with_plus(self, trigger):
        """Test numeric filter with + operator."""
        assert trigger._validate_numeric_filter("60+") is True

    def test_validate_numeric_filter_with_minus(self, trigger):
        """Test numeric filter with - operator."""
        assert trigger._validate_numeric_filter("30-") is True

    def test_validate_numeric_filter_plain_number(self, trigger):
        """Test numeric filter with plain number."""
        assert trigger._validate_numeric_filter("75") is True

    def test_validate_numeric_filter_empty(self, trigger):
        """Test empty numeric filter."""
        assert trigger._validate_numeric_filter("") is False

    def test_validate_numeric_filter_invalid(self, trigger):
        """Test invalid numeric filter."""
        assert trigger._validate_numeric_filter("abc") is False

    def test_validate_numeric_filter_negative(self, trigger):
        """Test negative number filter."""
        assert trigger._validate_numeric_filter("-5") is False

    # =============================================================================
    # URL Building Tests
    # =============================================================================

    def test_build_query_url_basic(self, trigger):
        """Test basic URL building."""
        url = trigger.build_query_url("malware")

        assert "https://www.virustotal.com/api/v3/threat_lists/malware/latest" in url
        assert "limit=1000" in url

    def test_build_query_url_with_ioc_types(self, trigger):
        """Test URL with IOC types filter uses 'type' parameter."""
        url = trigger.build_query_url("ransomware")

        assert "type=file%2Curl" in url or "type=file,url" in url

    def test_build_query_url_with_query(self, trigger):
        """Test URL with extra query params."""
        trigger.configuration["extra_query_params"] = "gti_score:60+"
        url = trigger.build_query_url("malware")

        assert "query=" in url

    def test_build_query_url_with_cursor(self, trigger):
        """Test URL with pagination cursor."""
        url = trigger.build_query_url("malware", cursor="abc123")

        assert "cursor=abc123" in url

    # =============================================================================
    # Type Filtering Tests (file-only threat lists)
    # =============================================================================

    def test_file_only_threat_list_returns_only_files(self, initialized_trigger):
        """Test that a file-only threat list (ransomware) returns file IOCs.

        Some threat lists (ransomware, cryptominer) only contain file IOCs.
        When requesting url/domain types the API returns an empty list, which
        should be handled gracefully (no crash, no error).
        """
        initialized_trigger.configuration["threat_list_id"] = "ransomware"
        initialized_trigger.configuration["ioc_types"] = ["url", "domain"]

        # API returns empty iocs when type filter is incompatible with list content
        empty_response = {"iocs": [], "meta": {}}

        with patch.object(initialized_trigger, "_make_request") as mock_req:
            mock_req.return_value = empty_response

            result = initialized_trigger.fetch_events()

        assert result["iocs"] == []
        initialized_trigger.log.assert_called()

    def test_file_only_threat_list_with_file_filter(self, initialized_trigger):
        """Test that requesting file type from a file-only list works normally."""
        initialized_trigger.configuration["threat_list_id"] = "cryptominer"
        initialized_trigger.configuration["ioc_types"] = ["file"]

        file_response = {
            "iocs": [
                {
                    "data": {
                        "type": "file",
                        "id": "abc123hash",
                        "attributes": {
                            "gti_assessment": {"threat_score": {"value": 80}},
                        },
                        "relationships": {},
                    }
                }
            ],
            "meta": {},
        }

        with patch.object(initialized_trigger, "_make_request") as mock_req:
            mock_req.return_value = file_response

            result = initialized_trigger.fetch_events()

        assert len(result["iocs"]) == 1
        assert result["iocs"][0]["data"]["type"] == "file"

    def test_transform_filters_empty_batch_gracefully(self, trigger):
        """Test that transforming and filtering an empty batch produces no events."""
        raw_iocs = []
        transformed = [trigger.transform_ioc(ioc) for ioc in raw_iocs]
        new_events = trigger.filter_new_events(transformed)

        assert new_events == []

    def test_run_empty_response_from_file_only_list(self, initialized_trigger):
        """Test run loop handles empty response from file-only list with incompatible filter."""
        initialized_trigger.configuration["threat_list_id"] = "ransomware"
        initialized_trigger.configuration["ioc_types"] = ["url"]

        empty_response = {"iocs": [], "meta": {}}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "_make_request") as mock_req:
            mock_req.return_value = empty_response
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                with patch(
                    "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
                ):
                    initialized_trigger.run()

        # Should log nothing_to_push, not crash
        assert any("nothing_to_push" in str(call) for call in initialized_trigger.log.call_args_list)

    # =============================================================================
    # HTTP Request Tests
    # =============================================================================

    def test_make_request_success(self, initialized_trigger, sample_vt_response):
        """Test successful API request."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_vt_response
            mock_get.return_value = mock_response

            result = initialized_trigger._make_request("https://example.com/api")

            assert result == sample_vt_response

    def test_make_request_rate_limit(self, initialized_trigger):
        """Test rate limit handling (429)."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_get.return_value = mock_response

            with pytest.raises(QuotaExceededError):
                initialized_trigger._make_request("https://example.com/api")

    def test_make_request_unauthorized(self, initialized_trigger):
        """Test unauthorized handling (401)."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response

            with pytest.raises(InvalidAPIKeyError):
                initialized_trigger._make_request("https://example.com/api")

    def test_make_request_forbidden(self, initialized_trigger):
        """Test forbidden handling (403)."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_get.return_value = mock_response

            with pytest.raises(InvalidAPIKeyError):
                initialized_trigger._make_request("https://example.com/api")

    def test_make_request_not_found(self, initialized_trigger):
        """Test not found handling (404)."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            with pytest.raises(ThreatListNotFoundError):
                initialized_trigger._make_request("https://example.com/api")

    def test_make_request_server_error(self, initialized_trigger):
        """Test server error handling (500+)."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            with pytest.raises(VirusTotalAPIError) as exc_info:
                initialized_trigger._make_request("https://example.com/api")

            assert "Server error" in str(exc_info.value)

    def test_make_request_other_error(self, initialized_trigger):
        """Test other error handling."""
        with patch.object(initialized_trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_get.return_value = mock_response

            with pytest.raises(VirusTotalAPIError) as exc_info:
                initialized_trigger._make_request("https://example.com/api")

            assert "400" in str(exc_info.value)

    # =============================================================================
    # Fetch Events Tests
    # =============================================================================

    def test_fetch_events_success(self, initialized_trigger, sample_vt_response):
        """Test successful event fetching."""
        with patch.object(initialized_trigger, "_make_request") as mock_request:
            mock_request.return_value = sample_vt_response

            result = initialized_trigger.fetch_events()

            assert result == sample_vt_response
            assert len(result["iocs"]) == 2
            initialized_trigger.log.assert_called()

    def test_fetch_events_with_cursor(self, initialized_trigger, sample_vt_response):
        """Test event fetching with pagination cursor."""
        with patch.object(initialized_trigger, "_make_request") as mock_request:
            mock_request.return_value = sample_vt_response

            initialized_trigger.fetch_events(cursor="abc123")

            # Verify cursor is passed to URL builder
            call_args = mock_request.call_args[0][0]
            assert "cursor=abc123" in call_args

    def test_fetch_events_validates_threat_list(self, initialized_trigger):
        """Test fetch_events validates threat list ID."""
        initialized_trigger.configuration["threat_list_id"] = "invalid-list"

        with pytest.raises(ThreatListNotFoundError):
            initialized_trigger.fetch_events()

    def test_fetch_events_validates_query(self, initialized_trigger):
        """Test fetch_events validates query syntax."""
        initialized_trigger.configuration["extra_query_params"] = "invalid:query"

        with pytest.raises(QueryValidationError):
            initialized_trigger.fetch_events()

    # =============================================================================
    # IOC Transformation Tests
    # =============================================================================

    def test_transform_ioc_file(self, trigger):
        """Test file IOC transformation with nested API structure."""
        ioc = {
            "data": {
                "type": "file",
                "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "attributes": {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "gti_assessment": {"threat_score": {"value": 75}},
                    "positives": 12,
                    "total_engines": 70,
                },
                "relationships": {
                    "malware_families": {
                        "data": [{"attributes": {"name": "Emotet"}}]
                    }
                },
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "file"
        assert result["value"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result["gti_score"] == 75
        assert result["positives"] == 12
        assert result["malware_families"] == ["Emotet"]
        assert "ioc_hash" in result

    def test_transform_ioc_url(self, trigger):
        """Test URL IOC transformation with nested API structure."""
        ioc = {
            "data": {
                "type": "url",
                "id": "urlid",
                "attributes": {
                    "url": "http://malicious.com/payload.exe",
                    "gti_assessment": {"threat_score": {"value": 82}},
                },
                "relationships": {},
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "url"
        assert result["value"] == "http://malicious.com/payload.exe"
        assert result["gti_score"] == 82

    def test_transform_ioc_ip_address(self, trigger):
        """Test IP address IOC transformation."""
        ioc = {
            "data": {
                "type": "ip_address",
                "id": "1.2.3.4",
                "attributes": {
                    "gti_assessment": {"threat_score": {"value": 60}},
                },
                "relationships": {},
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "ip_address"
        assert result["value"] == "1.2.3.4"
        assert result["gti_score"] == 60

    def test_transform_ioc_domain(self, trigger):
        """Test domain IOC transformation."""
        ioc = {
            "data": {
                "type": "domain",
                "id": "evil.com",
                "attributes": {
                    "gti_assessment": {"threat_score": {"value": 90}},
                },
                "relationships": {},
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "domain"
        assert result["value"] == "evil.com"
        assert result["gti_score"] == 90

    def test_transform_ioc_unknown_type(self, trigger):
        """Test unknown IOC type transformation."""
        ioc = {
            "data": {
                "type": "unknown",
                "id": "some-id",
                "attributes": {},
                "relationships": {},
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "unknown"
        assert result["value"] == "some-id"

    def test_transform_ioc_preserves_raw(self, trigger):
        """Test transform_ioc preserves raw IOC data (inner dict after unwrapping)."""
        ioc = {
            "data": {
                "type": "file",
                "id": "abc",
                "attributes": {},
                "relationships": {},
            }
        }

        result = trigger.transform_ioc(ioc)

        assert result["raw"] == ioc["data"]

    # =============================================================================
    # IOC Hash Computation Tests
    # =============================================================================

    def test_compute_ioc_hash(self, trigger):
        """Test IOC hash computation."""
        hash1 = trigger._compute_ioc_hash("file", "abc123")
        hash2 = trigger._compute_ioc_hash("file", "abc123")
        hash3 = trigger._compute_ioc_hash("file", "def456")

        assert hash1 == hash2  # Same input = same hash
        assert hash1 != hash3  # Different input = different hash

    def test_compute_ioc_hash_case_insensitive(self, trigger):
        """Test IOC hash is case-insensitive."""
        hash1 = trigger._compute_ioc_hash("file", "ABC123")
        hash2 = trigger._compute_ioc_hash("file", "abc123")

        assert hash1 == hash2

    def test_compute_ioc_hash_strips_whitespace(self, trigger):
        """Test IOC hash strips whitespace."""
        hash1 = trigger._compute_ioc_hash("file", "  abc123  ")
        hash2 = trigger._compute_ioc_hash("file", "abc123")

        assert hash1 == hash2

    # =============================================================================
    # Event Filtering (Deduplication) Tests
    # =============================================================================

    def test_filter_new_events(self, trigger):
        """Test event filtering (deduplication)."""
        events = [
            {"ioc_hash": "hash1", "data": "value1"},
            {"ioc_hash": "hash2", "data": "value2"},
            {"ioc_hash": "hash1", "data": "value3"},  # Duplicate
        ]

        new_events = trigger.filter_new_events(events)

        assert len(new_events) == 2
        assert new_events[0]["ioc_hash"] == "hash1"
        assert new_events[1]["ioc_hash"] == "hash2"

    def test_filter_new_events_subsequent_calls(self, trigger):
        """Test filtering remembers previously seen events."""
        events1 = [{"ioc_hash": "hash1", "data": "value1"}]
        trigger.filter_new_events(events1)

        events2 = [
            {"ioc_hash": "hash1", "data": "value2"},  # Already seen
            {"ioc_hash": "hash2", "data": "value3"},  # New
        ]
        new_events = trigger.filter_new_events(events2)

        assert len(new_events) == 1
        assert new_events[0]["ioc_hash"] == "hash2"

    def test_filter_events_without_hash_key(self, trigger):
        """Test filtering events without ioc_hash key."""
        events = [
            {"ioc_hash": "hash1", "data": "value1"},
            {"data": "value2"},  # Missing ioc_hash
            {"ioc_hash": "hash2", "data": "value3"},
        ]

        new_events = trigger.filter_new_events(events)

        assert len(new_events) == 2
        assert all("ioc_hash" in event for event in new_events)

    # =============================================================================
    # Push to SEKOIA Tests
    # =============================================================================

    def test_push_to_sekoia_no_values(self, trigger):
        """Test push_to_sekoia returns early on empty input."""
        trigger.push_to_sekoia([])
        assert any("No IOC values to push" in str(call) for call in trigger.log.call_args_list)

    def test_push_to_sekoia_missing_sekoia_api_key(self, trigger):
        """Test push_to_sekoia logs error without sekoia_api_key."""
        trigger.module.configuration["sekoia_api_key"] = ""
        trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])
        assert any("sekoia_api_key is not configured" in str(call) for call in trigger.log.call_args_list)

    def test_push_to_sekoia_missing_ioc_collection_uuid(self, trigger):
        """Test push_to_sekoia logs error without ioc_collection_uuid."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = ""
        trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])
        assert any("ioc_collection_uuid is not configured" in str(call) for call in trigger.log.call_args_list)

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limited_then_success(self, mock_sleep, trigger):
        """Test push_to_sekoia handles 429 then succeeds."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        rate_response = Mock()
        rate_response.status_code = 429
        rate_response.headers = {"Retry-After": "1"}
        rate_response.text = "rate limit"

        ok_response = Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"created": 1, "updated": 0, "ignored": 0}
        ok_response.text = ""

        mock_session = Mock()
        mock_session.post.side_effect = [rate_response, ok_response]

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        assert mock_sleep.called

    def test_push_to_sekoia_auth_error(self, trigger):
        """Test push_to_sekoia raises on auth error."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        response = Mock()
        response.status_code = 401
        response.text = "unauthorized"

        mock_session = Mock()
        mock_session.post.return_value = response

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            with pytest.raises(InvalidAPIKeyError):
                trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

    def test_push_to_sekoia_not_found(self, trigger):
        """Test push_to_sekoia raises on 404."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        response = Mock()
        response.status_code = 404
        response.text = "not found"

        mock_session = Mock()
        mock_session.post.return_value = response

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            with pytest.raises(VirusTotalAPIError):
                trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

    def test_push_to_sekoia_client_error(self, trigger):
        """Test push_to_sekoia raises on 4xx client error."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        response = Mock()
        response.status_code = 400
        response.text = "bad request"

        mock_session = Mock()
        mock_session.post.return_value = response

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            with pytest.raises(VirusTotalAPIError):
                trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_server_error_retries(self, mock_sleep, trigger):
        """Test push_to_sekoia retries on server error and logs failure."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        response = Mock()
        response.status_code = 500
        response.text = "server error"

        mock_session = Mock()
        mock_session.post.side_effect = [response, response, response]

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        assert any("Failed to push batch" in str(call) for call in trigger.log.call_args_list)

    def test_push_to_sekoia_sends_enriched_payload(self, trigger):
        """Test push_to_sekoia builds indicators with STIX types and valid_from."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        ok_response = Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"created": 2, "updated": 0, "ignored": 0}

        mock_session = Mock()
        mock_session.post.return_value = ok_response

        iocs = [
            {"value": "1.2.3.4", "type": "ip_address", "valid_from": "2024-01-15T00:00:00Z"},
            {"value": "abc123", "type": "file", "valid_from": None},
        ]

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia(iocs)

        # Verify the JSON payload sent
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        assert len(payload["indicators"]) == 2

        # IP → ipv4-addr.value with valid_from
        assert payload["indicators"][0]["type"] == "ipv4-addr.value"
        assert payload["indicators"][0]["value"] == "1.2.3.4"
        assert payload["indicators"][0]["valid_from"] == "2024-01-15T00:00:00Z"

        # File → file.hashes.'SHA-256', no valid_from when None
        assert payload["indicators"][1]["type"] == "file.hashes.'SHA-256'"
        assert "valid_from" not in payload["indicators"][1]

        # Enriched endpoint (not /indicators/text)
        url = call_args[0][0]
        assert url.endswith("/indicators")
        assert "/indicators/text" not in url

    def test_push_to_sekoia_stix_type_mapping(self, trigger):
        """Test all VT types map to correct STIX types."""
        from googlethreatintelligence.triggers.threat_list_to_ioc_collection import (
            GoogleThreatIntelligenceThreatListToIOCCollectionTrigger as Trigger,
        )

        assert Trigger._build_indicator({"value": "x", "type": "file"})["type"] == "file.hashes.'SHA-256'"
        assert Trigger._build_indicator({"value": "x", "type": "url"})["type"] == "url.value"
        assert Trigger._build_indicator({"value": "x", "type": "ip_address"})["type"] == "ipv4-addr.value"
        assert Trigger._build_indicator({"value": "x", "type": "domain"})["type"] == "domain-name.value"

    def test_transform_ioc_extracts_valid_from(self, trigger):
        """Test transform_ioc converts first_submission_date to valid_from ISO 8601."""
        ioc = {
            "data": {
                "type": "file",
                "id": "abc123",
                "attributes": {
                    "first_submission_date": 1705276800,  # 2024-01-15T00:00:00Z
                },
                "relationships": {},
            }
        }
        result = trigger.transform_ioc(ioc)
        assert result["valid_from"] == "2024-01-15T00:00:00Z"

    def test_transform_ioc_valid_from_none_when_missing(self, trigger):
        """Test transform_ioc sets valid_from to None when first_submission_date is absent."""
        ioc = {
            "data": {
                "type": "file",
                "id": "abc123",
                "attributes": {},
                "relationships": {},
            }
        }
        result = trigger.transform_ioc(ioc)
        assert result["valid_from"] is None

    def test_context_store_fallback(self, trigger):
        """Test context store falls back to local dict."""
        delattr(trigger, "context")
        store = trigger._get_context_store()
        assert store == {}

    def test_context_store_reuses_local_context(self, trigger):
        """Test _get_context_store reuses existing _local_context (L680→682)."""
        delattr(trigger, "context")
        store1 = trigger._get_context_store()
        store1["test"] = "value"
        store2 = trigger._get_context_store()
        assert store2["test"] == "value"
        assert store1 is store2

    def test_initialize_client_unexpected_status_code(self, trigger, requests_mock):
        """Test connectivity check with unexpected status code (L246)."""
        requests_mock.get(VT_USERS_CURRENT_URL, status_code=418)

        trigger.initialize_client()

        assert trigger.session is not None
        assert any("unexpected HTTP 418" in str(call) for call in trigger.log.call_args_list)

    def test_build_query_url_with_extra_query_params(self, trigger):
        """Test URL building includes extra_query_params (L341→345)."""
        trigger.configuration["extra_query_params"] = "gti_score:80+"
        url = trigger.build_query_url("malware")
        assert "query=" in url

    def test_transform_ioc_invalid_first_submission_date(self, trigger):
        """Test transform_ioc handles invalid first_submission_date (L454-455)."""
        ioc = {
            "data": {
                "type": "file",
                "id": "abc123",
                "attributes": {
                    "first_submission_date": "not-a-timestamp",
                },
                "relationships": {},
            }
        }
        result = trigger.transform_ioc(ioc)
        assert result["valid_from"] is None

    def test_transform_ioc_overflow_first_submission_date(self, trigger):
        """Test transform_ioc handles overflow first_submission_date (OSError)."""
        ioc = {
            "data": {
                "type": "file",
                "id": "abc123",
                "attributes": {
                    "first_submission_date": 99999999999999,  # overflow
                },
                "relationships": {},
            }
        }
        result = trigger.transform_ioc(ioc)
        assert result["valid_from"] is None

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_without_retry_after(self, mock_sleep, trigger):
        """Test push_to_sekoia uses exponential backoff when no Retry-After header (L607)."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        rate_response = Mock()
        rate_response.status_code = 429
        rate_response.headers = {}  # No Retry-After
        rate_response.text = "rate limit"

        ok_response = Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_session = Mock()
        mock_session.post.side_effect = [rate_response, ok_response]

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        # Exponential backoff: 2^0 * 10 = 10
        mock_sleep.assert_any_call(10)

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_with_retry_after(self, mock_sleep, trigger):
        """Test push_to_sekoia uses Retry-After header value (L607)."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        rate_response = Mock()
        rate_response.status_code = 429
        rate_response.headers = {"Retry-After": "42"}
        rate_response.text = "rate limit"

        ok_response = Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_session = Mock()
        mock_session.post.side_effect = [rate_response, ok_response]

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        mock_sleep.assert_any_call(42)

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_request_timeout(self, mock_sleep, trigger):
        """Test push_to_sekoia handles request timeout (L652-657)."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.Timeout("timed out")

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        assert any("Request timeout" in str(call) for call in trigger.log.call_args_list)
        assert any("Failed to push batch" in str(call) for call in trigger.log.call_args_list)

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_request_exception(self, mock_sleep, trigger):
        """Test push_to_sekoia handles RequestException (L659-664)."""
        trigger.module.configuration["sekoia_api_key"] = "sek-key"
        trigger.configuration["ioc_collection_uuid"] = "uuid-1"

        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.ConnectionError("refused")

        with patch(
            "googlethreatintelligence.triggers.threat_list_to_ioc_collection.requests.Session",
            return_value=mock_session,
        ):
            trigger.push_to_sekoia([{"value": "1.2.3.4", "type": "ip_address"}])

        assert any("Request error" in str(call) for call in trigger.log.call_args_list)

    @patch("googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep")
    def test_run_batch_empty_values(self, mock_sleep, initialized_trigger):
        """Test run logs batch_empty_values when IoCs have no value (L815)."""
        response = {
            "iocs": [
                {
                    "data": {
                        "type": "file",
                        "id": "",
                        "attributes": {},
                        "relationships": {},
                    }
                }
            ],
            "meta": {},
        }

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "_make_request") as mock_request:
            mock_request.return_value = response
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        assert any("batch_empty_values" in str(call) for call in initialized_trigger.log.call_args_list)

    # =============================================================================
    # Run Loop Tests
    # =============================================================================

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_initialization_failure(self, mock_sleep, trigger):
        """Test run method handles initialization failure."""
        trigger.module.configuration["api_key"] = ""

        trigger.run()

        # Should log failure and return early
        assert any(
            "Failed to initialize" in str(call) for call in trigger.log.call_args_list
        )

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_logs_resume_from_cursor(self, mock_sleep, initialized_trigger):
        """Test run method logs resume when cursor exists."""
        initialized_trigger.save_cursor("cursor123")

        with patch.object(
            type(initialized_trigger),
            "running",
            new_callable=lambda: property(lambda s: False),
        ):
            initialized_trigger.run()

        assert any("resume_from_cursor" in str(call) for call in initialized_trigger.log.call_args_list)

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_logs_nothing_to_push(self, mock_sleep, initialized_trigger):
        """Test run method logs when there is nothing to push."""
        response_no_data = {"iocs": [], "meta": {}}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "fetch_events") as mock_fetch:
            mock_fetch.return_value = response_no_data
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        assert any("nothing_to_push" in str(call) for call in initialized_trigger.log.call_args_list)

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_loop_one_iteration(self, mock_sleep, initialized_trigger, sample_vt_response):
        """Test run method executes one iteration successfully."""
        # Remove continuation cursor to exit after first fetch
        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {"count": 2}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "_make_request") as mock_request:
            mock_request.return_value = response_no_cursor
            with patch.object(initialized_trigger, "push_to_sekoia") as mock_push:
                with patch.object(
                    type(initialized_trigger),
                    "running",
                    new_callable=lambda: property(lambda s: mock_running()),
                ):
                    initialized_trigger.run()

        # Verify push_to_sekoia was called with IOC values
        assert mock_push.called

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_handles_fatal_error(self, mock_sleep, initialized_trigger):
        """Test run method handles fatal errors gracefully."""
        with patch.object(initialized_trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = InvalidAPIKeyError("Invalid key")

            call_count = 0

            def mock_running():
                nonlocal call_count
                call_count += 1
                return call_count <= 2

            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        # Should log fatal error
        assert any("Fatal error" in str(call) for call in initialized_trigger.log.call_args_list)

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_handles_recoverable_error(
        self, mock_sleep, initialized_trigger, sample_vt_response
    ):
        """Test run method handles recoverable errors and continues."""
        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 2

        with patch.object(initialized_trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = [
                Exception("Temporary error"),
                response_no_cursor,
            ]
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        # Should log error but continue
        assert any("Error in loop" in str(call) for call in initialized_trigger.log.call_args_list)
        # Sleep should be called for error recovery
        mock_sleep.assert_called()

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_handles_keyboard_interrupt(self, mock_sleep, initialized_trigger):
        """Test run method handles KeyboardInterrupt."""
        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = KeyboardInterrupt
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        assert any("stopped_by_user" in str(call) for call in initialized_trigger.log.call_args_list)

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_handles_quota_exceeded(self, mock_sleep, initialized_trigger):
        """Test run method handles quota exceeded errors."""
        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = QuotaExceededError("rate limit")
            with patch.object(
                type(initialized_trigger),
                "running",
                new_callable=lambda: property(lambda s: mock_running()),
            ):
                initialized_trigger.run()

        assert any("quota_exceeded" in str(call) for call in initialized_trigger.log.call_args_list)

    @patch(
        "googlethreatintelligence.triggers.threat_list_to_ioc_collection.time.sleep"
    )
    def test_run_sends_events(self, mock_sleep, initialized_trigger, sample_vt_response):
        """Test run method pushes IOCs to Sekoia."""
        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(initialized_trigger, "_make_request") as mock_request:
            mock_request.return_value = response_no_cursor
            with patch.object(initialized_trigger, "push_to_sekoia") as mock_push:
                with patch.object(
                    type(initialized_trigger),
                    "running",
                    new_callable=lambda: property(lambda s: mock_running()),
                ):
                    initialized_trigger.run()

        # Verify push_to_sekoia was called with IOC values (2 IOCs from sample response)
        assert mock_push.call_count == 1
        # Check the IOC values passed to push_to_sekoia
        ioc_values = mock_push.call_args[0][0]
        assert len(ioc_values) == 2


class TestExceptionClasses:
    """Test exception class attributes."""

    def test_quota_exceeded_error_retryable(self):
        """Test QuotaExceededError is marked as retryable."""
        assert QuotaExceededError.retryable is True

    def test_invalid_api_key_error_not_retryable(self):
        """Test InvalidAPIKeyError is not retryable."""
        assert InvalidAPIKeyError.retryable is False

    def test_threat_list_not_found_error_not_retryable(self):
        """Test ThreatListNotFoundError is not retryable."""
        assert ThreatListNotFoundError.retryable is False


class TestConstants:
    """Test module constants."""

    def test_valid_threat_list_ids_contains_expected(self):
        """Test VALID_THREAT_LIST_IDS contains expected values."""
        expected = [
        "ransomware",
        "malicious-network-infrastructure",
        "malware",
        "threat-actor",
        "trending",
        "mobile",
        "osx",
        "linux",
        "iot",
        "cryptominer",
        "phishing",
        "first-stage-delivery-vectors",
        "vulnerability-weaponization",
        "infostealer",
        ]
        assert set(VALID_THREAT_LIST_IDS) == set(expected)

    def test_valid_ioc_types_contains_expected(self):
        """Test VALID_IOC_TYPES contains expected values."""
        expected = ["file", "url", "ip_address", "domain"]
        assert VALID_IOC_TYPES == expected

    def test_valid_has_values_contains_expected(self):
        """Test VALID_HAS_VALUES contains expected values."""
        expected = ["malware_families", "campaigns", "reports", "threat_actors"]
        assert VALID_HAS_VALUES == expected
