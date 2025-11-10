from typing import Any, Dict
import requests_mock
import json
import urllib.parse

from googlethreatintelligence.get_ioc_report import GTIIoCReport

# === Test constants ===
HOST = "https://www.virustotal.com/api/v3/"
API_KEY = "FAKE_API_KEY"
IP = "8.8.8.8"
URI = ""

def _qs_matcher(expected_params: Dict[str, Any]):
    """
    Return a requests_mock additional_matcher that checks query params in request.qs
    """
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_get_ip_report_success():
    """Test successful get_ip_report action."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/api/v3/ip_addresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GET_IOC_REPORT_IP_ADDRESSES_OUTPUT["response"],
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_ip_report(IP)
        assert response is not None

        data = json.loads(response) if isinstance(response, str) else response
        assert data["entity"] == IP
        assert mock_requests.call_count == 1


def test_get_domain_report_success():
    """Test successful get_domain_report action."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    domain = "google.com"
    uri = f"/api/v3/domains/{domain}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GET_IOC_REPORT_DOMAINS_OUTPUT["response"],
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_domain_report(domain)
        assert response is not None

        data = json.loads(response) if isinstance(response, str) else response
        assert data["entity"] == domain
        assert "categories" in data
        assert mock_requests.call_count == 1


def test_get_url_report_success():
    """Test successful get_url_report action."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    url_id = GET_IOC_REPORT_URLS_OUTPUT["response"]["entity"]
    uri = f"/api/v3/urls/{url_id}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GET_IOC_REPORT_URLS_OUTPUT["response"],
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_url_report(url_id)
        assert response is not None

        data = json.loads(response) if isinstance(response, str) else response
        assert data["entity"] == url_id
        assert mock_requests.call_count == 1


def test_get_file_report_success():
    """Test successful get_file_report action."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    file_hash = GET_IOC_REPORT_FILES_OUTPUT["response"]["entity"]
    uri = f"/api/v3/files/{file_hash}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GET_IOC_REPORT_FILES_OUTPUT["response"],
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_file_report(file_hash)
        assert response is not None

        data = json.loads(response) if isinstance(response, str) else response
        assert data["entity"] == file_hash
        assert mock_requests.call_count == 1


def test_get_ip_report_not_found():
    """Test get_ip_report when resource not found (404)."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/api/v3/ip_addresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"code": 404, "message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_ip_report(IP)
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or "message" in data
        assert mock_requests.call_count == 1


def test_get_ip_report_api_error():
    """Test get_ip_report on API internal server error."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/api/v3/ip_addresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.get_ip_report(IP)
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or "Error" in str(data)
        assert mock_requests.call_count == 1

GET_IOC_REPORT_IP_ADDRESSES_OUTPUT: dict[str, Any] = {
    "name": "GET_IOC_REPORT_IP_ADDRESSES",
    "method": "GET",
    "endpoint": "/api/v3/ip_addresses/8.8.8.8",
    "status": "SUCCESS",
    "response": {
      "entity_type": "ip_addresses",
      "entity": "8.8.8.8",
      "id": "8.8.8.8",
      "reputation": 527,
      "last_analysis_stats": {
        "malicious": 0,
        "suspicious": 0,
        "undetected": 33,
        "harmless": 62,
        "timeout": 0
      },
      "country": "US"
    },
    "error": None
  }

GET_IOC_REPORT_DOMAINS_OUTPUT: dict[str, Any] = {
    "name": "GET_IOC_REPORT_DOMAINS",
    "method": "GET",
    "endpoint": "/api/v3/domains/google.com",
    "status": "SUCCESS",
    "response": {
      "entity_type": "domains",
      "entity": "google.com",
      "id": "google.com",
      "reputation": 656,
      "last_analysis_stats": {
        "malicious": 0,
        "suspicious": 0,
        "undetected": 27,
        "harmless": 68,
        "timeout": 0
      },
      "categories": {
        "alphaMountain.ai": "Translation (alphaMountain.ai)",
        "BitDefender": "education",
        "Xcitium Verdict Cloud": "search engines & portals",
        "Sophos": "translators",
        "Forcepoint ThreatSeeker": "reference materials"
      }
    },
    "error": None
  }

GET_IOC_REPORT_URLS_OUTPUT: dict[str, Any] = {
    "name": "GET_IOC_REPORT_URLS",
    "method": "GET",
    "endpoint": "/api/v3/urls/aHR0cHM6Ly93d3cuc2Vrb2lhLmlvL2VuL2hvbWVwYWdlLw",
    "status": "SUCCESS",
    "response": {
      "entity_type": "urls",
      "entity": "aHR0cHM6Ly93d3cuc2Vrb2lhLmlvL2VuL2hvbWVwYWdlLw",
      "id": "001deb5ff031b6c98a7379e212bb588f3f1b77d1a2eeb19470c5d118e96e99d1",
      "reputation": 0,
      "last_analysis_stats": {
        "malicious": 0,
        "suspicious": 0,
        "undetected": 30,
        "harmless": 68,
        "timeout": 0
      },
      "categories": {
        "BitDefender": "business",
        "Sophos": "information technology",
        "Forcepoint ThreatSeeker": "computer security"
      }
    },
    "error": None
  }

GET_IOC_REPORT_FILES_OUTPUT: dict[str, Any] = {
    "name": "GET_IOC_REPORT_FILES",
    "method": "GET",
    "endpoint": "/api/v3/files/44d88612fea8a8f36de82e1278abb02f",
    "status": "SUCCESS",
    "response": {
      "entity_type": "files",
      "entity": "44d88612fea8a8f36de82e1278abb02f",
      "id": "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
      "reputation": 3697,
      "last_analysis_stats": {
        "malicious": 66,
        "suspicious": 0,
        "undetected": 4,
        "harmless": 0,
        "timeout": 0,
        "confirmed-timeout": 0,
        "failure": 0,
        "type-unsupported": 7
      }
    },
    "error": None
  }
