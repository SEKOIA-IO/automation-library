"""
Unit tests for GoogleThreatIntelligenceThreatListToIOCCollectionTrigger

Tests the VirusTotal API-based GTI Threat List connector per SOW specification.
"""
import pytest
from unittest.mock import Mock, patch

from google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection import (
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
            "virustotal_api_key": valid_api_key,
        }

        trigger = GoogleThreatIntelligenceThreatListToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {
            "sleep_time": "300",
            "threat_list_id": "malware",
            "ioc_types": ["file", "url"],
            "max_iocs": 1000,
        }
        trigger.log = Mock()
        trigger.send_event = Mock()
        return trigger

    @pytest.fixture
    def sample_vt_response(self):
        """Sample VirusTotal API response."""
        return {
            "data": [
                {
                    "type": "file",
                    "id": "abc123def456",
                    "attributes": {
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "md5": "d41d8cd98f00b204e9800998ecf8427e",
                        "gti_score": 75,
                        "positives": 12,
                        "total_engines": 70,
                        "malware_families": ["Emotet"],
                        "campaigns": ["campaign-2024"],
                        "threat_actors": ["APT29"],
                    },
                },
                {
                    "type": "url",
                    "id": "http://malicious.com/payload.exe",
                    "attributes": {
                        "url": "http://malicious.com/payload.exe",
                        "gti_score": 82,
                        "positives": 15,
                        "total_engines": 80,
                    },
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
        assert trigger.sleep_time == 300
        assert trigger.processed_events is not None
        assert trigger.session is None

    def test_sleep_time_property(self, trigger):
        """Test sleep_time property returns configured value."""
        trigger.configuration["sleep_time"] = "600"
        assert trigger.sleep_time == 600

    def test_sleep_time_default(self, trigger):
        """Test sleep_time default value."""
        trigger.configuration = {}
        assert trigger.sleep_time == 300

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

    # =============================================================================
    # Client Initialization Tests
    # =============================================================================

    def test_initialize_client_success(self, trigger):
        """Test successful client initialization."""
        trigger.initialize_client()

        assert trigger.session is not None
        assert trigger.session.headers["X-Apikey"] == trigger.api_key
        assert trigger.session.headers["Accept"] == "application/json"
        trigger.log.assert_called()

    def test_initialize_client_missing_api_key(self, trigger):
        """Test client initialization fails without API key."""
        trigger.module.configuration["virustotal_api_key"] = ""

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "API key is required" in str(exc_info.value)

    def test_initialize_client_invalid_api_key_format(self, trigger):
        """Test client initialization fails with invalid API key format."""
        trigger.module.configuration["virustotal_api_key"] = "short_key"

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            trigger.initialize_client()

        assert "Invalid VirusTotal API key format" in str(exc_info.value)

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
        """Test URL with IOC types filter."""
        url = trigger.build_query_url("ransomware")

        assert "ioc_types=file%2Curl" in url or "ioc_types=file,url" in url

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
    # HTTP Request Tests
    # =============================================================================

    def test_make_request_success(self, trigger, sample_vt_response):
        """Test successful API request."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_vt_response
            mock_get.return_value = mock_response

            result = trigger._make_request("https://example.com/api")

            assert result == sample_vt_response

    def test_make_request_rate_limit(self, trigger):
        """Test rate limit handling (429)."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_get.return_value = mock_response

            with pytest.raises(QuotaExceededError):
                trigger._make_request("https://example.com/api")

    def test_make_request_unauthorized(self, trigger):
        """Test unauthorized handling (401)."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response

            with pytest.raises(InvalidAPIKeyError):
                trigger._make_request("https://example.com/api")

    def test_make_request_forbidden(self, trigger):
        """Test forbidden handling (403)."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_get.return_value = mock_response

            with pytest.raises(InvalidAPIKeyError):
                trigger._make_request("https://example.com/api")

    def test_make_request_not_found(self, trigger):
        """Test not found handling (404)."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            with pytest.raises(ThreatListNotFoundError):
                trigger._make_request("https://example.com/api")

    def test_make_request_server_error(self, trigger):
        """Test server error handling (500+)."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            with pytest.raises(VirusTotalAPIError) as exc_info:
                trigger._make_request("https://example.com/api")

            assert "Server error" in str(exc_info.value)

    def test_make_request_other_error(self, trigger):
        """Test other error handling."""
        trigger.initialize_client()

        with patch.object(trigger.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_get.return_value = mock_response

            with pytest.raises(VirusTotalAPIError) as exc_info:
                trigger._make_request("https://example.com/api")

            assert "400" in str(exc_info.value)

    # =============================================================================
    # Fetch Events Tests
    # =============================================================================

    def test_fetch_events_success(self, trigger, sample_vt_response):
        """Test successful event fetching."""
        trigger.initialize_client()

        with patch.object(trigger, "_make_request") as mock_request:
            mock_request.return_value = sample_vt_response

            result = trigger.fetch_events()

            assert result == sample_vt_response
            assert len(result["data"]) == 2
            trigger.log.assert_called()

    def test_fetch_events_with_cursor(self, trigger, sample_vt_response):
        """Test event fetching with pagination cursor."""
        trigger.initialize_client()

        with patch.object(trigger, "_make_request") as mock_request:
            mock_request.return_value = sample_vt_response

            result = trigger.fetch_events(cursor="abc123")

            # Verify cursor is passed to URL builder
            call_args = mock_request.call_args[0][0]
            assert "cursor=abc123" in call_args

    def test_fetch_events_validates_threat_list(self, trigger):
        """Test fetch_events validates threat list ID."""
        trigger.configuration["threat_list_id"] = "invalid-list"
        trigger.initialize_client()

        with pytest.raises(ThreatListNotFoundError):
            trigger.fetch_events()

    def test_fetch_events_validates_query(self, trigger):
        """Test fetch_events validates query syntax."""
        trigger.configuration["extra_query_params"] = "invalid:query"
        trigger.initialize_client()

        with pytest.raises(QueryValidationError):
            trigger.fetch_events()

    # =============================================================================
    # IOC Transformation Tests
    # =============================================================================

    def test_transform_ioc_file(self, trigger):
        """Test file IOC transformation."""
        ioc = {
            "type": "file",
            "id": "abc123",
            "attributes": {
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "gti_score": 75,
                "positives": 12,
                "malware_families": ["Emotet"],
            },
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "file"
        assert result["value"] == ioc["attributes"]["sha256"]
        assert result["gti_score"] == 75
        assert result["positives"] == 12
        assert result["malware_families"] == ["Emotet"]
        assert "ioc_hash" in result

    def test_transform_ioc_url(self, trigger):
        """Test URL IOC transformation."""
        ioc = {
            "type": "url",
            "id": "urlid",
            "attributes": {
                "url": "http://malicious.com/payload.exe",
                "gti_score": 82,
            },
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "url"
        assert result["value"] == "http://malicious.com/payload.exe"
        assert result["gti_score"] == 82

    def test_transform_ioc_ip_address(self, trigger):
        """Test IP address IOC transformation."""
        ioc = {
            "type": "ip_address",
            "id": "1.2.3.4",
            "attributes": {
                "gti_score": 60,
            },
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "ip_address"
        assert result["value"] == "1.2.3.4"

    def test_transform_ioc_domain(self, trigger):
        """Test domain IOC transformation."""
        ioc = {
            "type": "domain",
            "id": "evil.com",
            "attributes": {
                "gti_score": 90,
            },
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "domain"
        assert result["value"] == "evil.com"

    def test_transform_ioc_unknown_type(self, trigger):
        """Test unknown IOC type transformation."""
        ioc = {
            "type": "unknown",
            "id": "some-id",
            "attributes": {},
        }

        result = trigger.transform_ioc(ioc)

        assert result["type"] == "unknown"
        assert result["value"] == "some-id"

    def test_transform_ioc_preserves_raw(self, trigger):
        """Test transform_ioc preserves raw IOC data."""
        ioc = {
            "type": "file",
            "id": "abc",
            "attributes": {"sha256": "hash123"},
        }

        result = trigger.transform_ioc(ioc)

        assert result["raw"] == ioc

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
    # Run Loop Tests
    # =============================================================================

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    def test_run_initialization_failure(self, mock_sleep, trigger):
        """Test run method handles initialization failure."""
        trigger.module.configuration["virustotal_api_key"] = ""

        trigger.run()

        # Should log failure and return early
        assert any(
            "Failed to initialize" in str(call) for call in trigger.log.call_args_list
        )

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    def test_run_loop_one_iteration(self, mock_sleep, trigger, sample_vt_response):
        """Test run method executes one iteration successfully."""
        trigger.initialize_client()

        # Remove continuation cursor to exit after first fetch
        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {"count": 2}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(trigger, "_make_request") as mock_request:
            mock_request.return_value = response_no_cursor
            with patch.object(trigger, "push_to_sekoia") as mock_push:
                with patch.object(
                    type(trigger), "running", new_callable=lambda: property(lambda s: mock_running())
                ):
                    trigger.run()

        # Verify push_to_sekoia was called with IOC values
        assert mock_push.called

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    def test_run_handles_fatal_error(self, mock_sleep, trigger):
        """Test run method handles fatal errors gracefully."""
        trigger.initialize_client()

        with patch.object(trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = InvalidAPIKeyError("Invalid key")

            call_count = 0

            def mock_running():
                nonlocal call_count
                call_count += 1
                return call_count <= 2

            with patch.object(
                type(trigger), "running", new_callable=lambda: property(lambda s: mock_running())
            ):
                trigger.run()

        # Should log fatal error
        assert any("Fatal error" in str(call) for call in trigger.log.call_args_list)

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    def test_run_handles_recoverable_error(self, mock_sleep, trigger, sample_vt_response):
        """Test run method handles recoverable errors and continues."""
        trigger.initialize_client()

        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 2

        with patch.object(trigger, "fetch_events") as mock_fetch:
            mock_fetch.side_effect = [
                Exception("Temporary error"),
                response_no_cursor,
            ]
            with patch.object(
                type(trigger), "running", new_callable=lambda: property(lambda s: mock_running())
            ):
                trigger.run()

        # Should log error but continue
        assert any("Error in loop" in str(call) for call in trigger.log.call_args_list)
        # Sleep should be called for error recovery
        mock_sleep.assert_called()

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    def test_run_sends_events(self, mock_sleep, trigger, sample_vt_response):
        """Test run method pushes IOCs to Sekoia."""
        trigger.initialize_client()

        response_no_cursor = sample_vt_response.copy()
        response_no_cursor["meta"] = {}

        call_count = 0

        def mock_running():
            nonlocal call_count
            call_count += 1
            return call_count <= 1

        with patch.object(trigger, "_make_request") as mock_request:
            mock_request.return_value = response_no_cursor
            with patch.object(trigger, "push_to_sekoia") as mock_push:
                with patch.object(
                    type(trigger), "running", new_callable=lambda: property(lambda s: mock_running())
                ):
                    trigger.run()

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
            "malware",
            "phishing",
            "threat-actor",
            "infostealer",
        ]
        for item in expected:
            assert item in VALID_THREAT_LIST_IDS

    def test_valid_ioc_types_contains_expected(self):
        """Test VALID_IOC_TYPES contains expected values."""
        expected = ["file", "url", "ip_address", "domain"]
        assert VALID_IOC_TYPES == expected

    def test_valid_has_values_contains_expected(self):
        """Test VALID_HAS_VALUES contains expected values."""
        expected = ["malware_families", "campaigns", "reports", "threat_actors"]
        assert VALID_HAS_VALUES == expected
