import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection import GoogleThreatIntelligenceThreatListToIOCCollectionTrigger


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
    def trigger(self):
        """Create trigger instance."""
        mock_module = Mock()
        mock_module.configuration = {
            "google_threat_intelligence_url": "https://misp.example.com",
            "google_threat_intelligence_api_key": "test_key",
        }
        
        trigger = GoogleThreatIntelligenceThreatListToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {"sleep_time": "300"}
        trigger._logger = Mock()
        trigger.log = Mock()
        return trigger
    
    def test_initialization(self, trigger):
        """Test trigger initialization."""
        assert trigger.sleep_time == 300
        assert trigger.processed_events is not None
    
    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_initialize_client_success(self, mock_pymisp, trigger):
        """Test successful client initialization."""
        client = Mock()
        mock_pymisp.return_value = client
        
        trigger.initialize_client()
        
        assert trigger.client == client
        mock_pymisp.assert_called_once()
    
    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_initialize_client_error(self, mock_pymisp, trigger):
        """Test client initialization error handling."""
        mock_pymisp.side_effect = Exception("Connection failed")

        with pytest.raises(Exception) as exc_info:
            trigger.initialize_client()

        assert "Connection failed" in str(exc_info.value)
        trigger.log.assert_called()

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_fetch_events(self, mock_pymisp, trigger):
        """Test fetching events."""
        client = Mock()
        client.search.return_value = [
            Mock(uuid="1", type="ip-dst", value="1.1.1.1"),
            Mock(uuid="2", type="domain", value="evil.com"),
        ]
        mock_pymisp.return_value = client

        trigger.initialize_client()
        events = trigger.fetch_events()

        assert len(events) == 2
        client.search.assert_called_once()

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_fetch_events_error(self, mock_pymisp, trigger):
        """Test fetch events error handling."""
        client = Mock()
        client.search.side_effect = Exception("API Error")
        mock_pymisp.return_value = client

        trigger.initialize_client()

        with pytest.raises(Exception) as exc_info:
            trigger.fetch_events()

        assert "API Error" in str(exc_info.value)
        trigger.log.assert_called()

    def test_filter_new_events(self, trigger):
        """Test event filtering (deduplication)."""
        events = [
            {"ioc_hash": "event1", "data": "value1"},
            {"ioc_hash": "event2", "data": "value2"},
            {"ioc_hash": "event1", "data": "value3"},  # Duplicate
        ]

        new_events = trigger.filter_new_events(events)

        assert len(new_events) == 2
        assert new_events[0]["ioc_hash"] == "event1"
        assert new_events[1]["ioc_hash"] == "event2"

        # Test that subsequent calls filter out previously seen events
        more_events = [
            {"ioc_hash": "event1", "data": "value4"},  # Already seen
            {"ioc_hash": "event3", "data": "value5"},  # New
        ]

        new_events2 = trigger.filter_new_events(more_events)

        assert len(new_events2) == 1
        assert new_events2[0]["ioc_hash"] == "event3"

    def test_filter_events_without_key(self, trigger):
        """Test filtering events that don't have the deduplication key."""
        events = [
            {"ioc_hash": "event1", "data": "value1"},
            {"data": "value2"},  # Missing key field
            {"ioc_hash": "event2", "data": "value3"},
        ]

        new_events = trigger.filter_new_events(events)

        # Only events with the key field should be processed
        assert len(new_events) == 2
        assert all("ioc_hash" in event for event in new_events)

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISPError", Exception)
    def test_fetch_events_pymisp_error(self, mock_pymisp, trigger):
        """Test fetch events with PyMISP-specific error."""
        client = Mock()
        pymisp_error = Exception("PyMISP API Error")
        client.search.side_effect = pymisp_error
        mock_pymisp.return_value = client

        trigger.initialize_client()

        with pytest.raises(Exception) as exc_info:
            trigger.fetch_events()

        assert "PyMISP API Error" in str(exc_info.value)
        trigger.log.assert_called()

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_run_loop_one_iteration(self, mock_pymisp, mock_sleep, trigger):
        """Test run method executes one iteration successfully."""
        client = Mock()
        client.search.return_value = [
            {"ioc_hash": "event1", "data": "value1"}
        ]
        mock_pymisp.return_value = client

        # Mock running property to return True once, then False
        with patch.object(type(trigger), 'running', new_callable=lambda: property(lambda self: mock_running.pop(0))):
            mock_running = [True, False]  # Run once then stop
            trigger.run()

        # Verify initialization was called
        mock_pymisp.assert_called_once()
        # Verify events were fetched
        client.search.assert_called()
        # Verify sleep was called
        mock_sleep.assert_called()

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_run_initialization_failure(self, mock_pymisp, trigger):
        """Test run method handles initialization failure."""
        mock_pymisp.side_effect = Exception("Initialization failed")

        trigger.run()

        # Should log failure and return early
        trigger.log.assert_called()
        assert any("Failed to initialize" in str(call) for call in trigger.log.call_args_list)

    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.time.sleep")
    @patch("google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection.PyMISP")
    def test_run_loop_exception_handling(self, mock_pymisp, mock_sleep, trigger):
        """Test run method handles exceptions in the loop."""
        client = Mock()
        client.search.side_effect = [
            Exception("Temporary error"),
            []  # Second call succeeds with empty list
        ]
        mock_pymisp.return_value = client

        # Mock running property to return True twice, then False
        with patch.object(type(trigger), 'running', new_callable=lambda: property(lambda self: mock_running.pop(0) if mock_running else False)):
            mock_running = [True, True, False]  # Run twice then stop
            trigger.run()

        # Verify error was logged
        assert any("Error in loop" in str(call) for call in trigger.log.call_args_list)
        # Verify sleep was called (including error recovery sleep)
        assert mock_sleep.call_count >= 1