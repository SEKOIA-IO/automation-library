"""
Pytest fixtures for GoogleThreatIntelligenceThreatListToIOCCollectionTrigger tests
Auto-generated from AKONIS Integration Standard v0.1.0
"""
import pytest


@pytest.fixture
def google_threat_intelligence_base_url():
    """Base URL for mock GoogleThreatIntelligenceModule server."""
    yield "https://mock-google_threat_intelligence.example.com/"


@pytest.fixture
def google_threat_intelligence_api_key():
    """Mock API key for testing."""
    yield "test-api-key-12345"


@pytest.fixture
def google_threat_intelligence_configuration(google_threat_intelligence_base_url, google_threat_intelligence_api_key):
    """Mock module configuration."""
    return {
        "google_threat_intelligence_url": google_threat_intelligence_base_url,
        "google_threat_intelligence_api_key": google_threat_intelligence_api_key,
    }


@pytest.fixture
def trigger_configuration():
    """Mock trigger configuration."""
    return {
        "sleep_time": 60,
    }


@pytest.fixture
def sample_event():
    """Sample event for testing."""
    return {
        "id": "test-event-1",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "type": "test",
        "timestamp": "2024-01-01T00:00:00Z",
        "data": {
            "field1": "value1",
            "field2": "value2",
        }
    }


@pytest.fixture
def sample_events(sample_event):
    """Multiple sample events for testing."""
    return [
        sample_event,
        {
            "id": "test-event-2",
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "type": "test",
            "timestamp": "2024-01-01T00:01:00Z",
            "data": {
                "field1": "value3",
                "field2": "value4",
            }
        }
    ]