from typing import Any, Dict
import requests_mock
import json

from domaintools.get_lookup_domain import DomaintoolsLookupDomain

import datetime
import urllib.parse
import hmac
import hashlib

DOMAIN: str = "google.com"
HOST = "https://api.domaintools.com/"
URI = f"v1/iris-investigate/"  # Base URI without domain
API_KEY = "LOREM"
API_USERNAME = "IPSUM"
TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(api_username, api_key, timestamp, uri):
    params = "".join([api_username, timestamp, uri])
    return hmac.new(api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1).hexdigest()


signature = sign(API_USERNAME, API_KEY, TIMESTAMP, URI)

ACTION = "lookup_domain"

DT_OUTPUT: dict[str, Any] = {
    "response": {
        "limit_exceeded": False,
        "has_more_results": False,
        "message": "Enjoy your data.",
        "results_count": 1,
        "total_count": 1,
        "results": [
            {
                "domain": "google.com",
                "whois_url": "https://whois.domaintools.com/google.com",
                "adsense": {"value": "", "count": 0},
            }
        ],
    }
}


def _qs_matcher(expected_params: Dict[str, Any]):
    """
    returns a requests_mock additional_matcher that checks specific params in request.qs
    """

    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        # Check that all expected params are present with correct values
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True

    return matcher


def test_get_lookup_domain_action_success():
    action = DomaintoolsLookupDomain()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        # Mock the actual URL that will be called (including domain parameter)
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            json=DT_OUTPUT,  # Return the expected response
            additional_matcher=_qs_matcher(
                {
                    # "api_username": API_USERNAME,
                    # "signature": signature,
                    # "timestamp": TIMESTAMP,
                    "domain": DOMAIN  # Add the domain parameter
                }
            ),
        )
        result = action.run({"domain": DOMAIN})

        assert result is not None

        # Parse the result - it might be nested in a wrapper
        data = json.loads(result)

        # Debug: print the actual structure
        print("Result structure:", json.dumps(data, indent=2))

        # Adjust assertion based on your actual return structure
        # If your action wraps the response, you might need something like:
        # assert data["Domain Reputation"]["results"][0]["domain"] == DOMAIN
        # Or if it returns the raw API response:
        assert data["results"][0]["domain"] == DOMAIN
        assert mock_requests.call_count == 1


def test_get_lookup_domain_action_api_error():
    action = DomaintoolsLookupDomain()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            status_code=500,  # Return an error status
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher(
                {
                    # "api_username": API_USERNAME,
                    # "signature": signature,
                    # "timestamp": TIMESTAMP,
                    "domain": DOMAIN  # Add the domain parameter
                }
            ),
        )
        result = action.run({"domain": DOMAIN})

        # Debug: print the actual result
        print("Error result:", result)

        # Parse and check for error
        if result:
            data = json.loads(result)
            # Check if there's an error in the response
            assert "error" in data or "Error" in str(data)
        else:
            # If your action returns None/False on error
            assert not result

        assert mock_requests.call_count == 1
