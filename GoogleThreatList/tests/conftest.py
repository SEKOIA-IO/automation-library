"""
Pytest fixtures for GoogleThreatIntelligenceThreatListToIOCCollectionTrigger tests

Tests the VirusTotal API-based GTI Threat List connector per SOW specification.
"""

import pytest


@pytest.fixture
def virustotal_base_url():
    """Base URL for VirusTotal API."""
    return "https://www.virustotal.com/api/v3"


@pytest.fixture
def virustotal_api_key():
    """Mock API key for testing (64 characters)."""
    return "a" * 64


@pytest.fixture
def module_configuration(virustotal_api_key):
    """Mock module configuration."""
    return {
        "virustotal_api_key": virustotal_api_key,
    }


@pytest.fixture
def trigger_configuration():
    """Mock trigger configuration."""
    return {
        "sleep_time": 60,
        "threat_list_id": "malware",
        "ioc_types": ["file", "url", "ip_address", "domain"],
        "max_iocs": 1000,
        "extra_query_params": "",
    }


@pytest.fixture
def sample_file_ioc():
    """Sample file IOC from VirusTotal API."""
    return {
        "type": "file",
        "id": "abc123def456",
        "attributes": {
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "md5": "d41d8cd98f00b204e9800998ecf8427e",
            "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
            "gti_score": 75,
            "positives": 12,
            "total_engines": 70,
            "malware_families": ["Emotet", "Trickbot"],
            "campaigns": ["campaign-2024-q1"],
            "threat_actors": ["APT29"],
        },
    }


@pytest.fixture
def sample_url_ioc():
    """Sample URL IOC from VirusTotal API."""
    return {
        "type": "url",
        "id": "http://malicious.com/payload.exe",
        "attributes": {
            "url": "http://malicious.com/payload.exe",
            "gti_score": 82,
            "positives": 15,
            "total_engines": 80,
            "categories": ["malware", "phishing"],
        },
    }


@pytest.fixture
def sample_ip_ioc():
    """Sample IP address IOC from VirusTotal API."""
    return {
        "type": "ip_address",
        "id": "192.168.1.1",
        "attributes": {
            "gti_score": 60,
            "positives": 5,
            "total_engines": 50,
        },
    }


@pytest.fixture
def sample_domain_ioc():
    """Sample domain IOC from VirusTotal API."""
    return {
        "type": "domain",
        "id": "evil.example.com",
        "attributes": {
            "gti_score": 90,
            "positives": 20,
            "total_engines": 60,
        },
    }


@pytest.fixture
def sample_vt_response(sample_file_ioc, sample_url_ioc):
    """Sample VirusTotal API response with multiple IoCs."""
    return {
        "data": [sample_file_ioc, sample_url_ioc],
        "meta": {
            "continuation_cursor": "eyJwYWdlIjoyLCJvZmZzZXQiOjEwMDB9",
            "count": 2,
        },
    }


@pytest.fixture
def sample_vt_response_no_cursor(sample_file_ioc, sample_url_ioc):
    """Sample VirusTotal API response without pagination cursor."""
    return {
        "data": [sample_file_ioc, sample_url_ioc],
        "meta": {
            "count": 2,
        },
    }


@pytest.fixture
def sample_vt_empty_response():
    """Sample empty VirusTotal API response."""
    return {
        "data": [],
        "meta": {
            "count": 0,
        },
    }
