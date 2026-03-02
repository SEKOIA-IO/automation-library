from typing import Any, Dict
import requests_mock
import json

from domaintools.get_reverse_domain import DomaintoolsReverseDomain

import datetime
import urllib.parse
import hmac
import hashlib

DOMAIN: str = "google.com"
HOST = "https://api.domaintools.com/"
# URI = f"v1/iris-investigate/"  # Base URI without domain
URI = f"/v1/{DOMAIN}/hosting-history/"
API_KEY = "LOREM"
API_USERNAME = "IPSUM"
TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(api_username, api_key, timestamp, uri):
    params = "".join([api_username, timestamp, uri])
    return hmac.new(api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1).hexdigest()


signature = sign(API_USERNAME, API_KEY, TIMESTAMP, URI)

ACTION = "reverse_domain"

DT_OUTPUT: dict[str, Any] = {
    "response": {
        "domain_name": "google.com",
        "ip_history": [
            {
                "domain": "GOOGLE.COM",
                "post_ip": "216.239.57.99",
                "pre_ip": None,
                "action": "N",
                "actiondate": "2004-04-24",
                "action_in_words": "New",
            },
            {
                "domain": "GOOGLE.COM",
                "post_ip": "66.102.7.99",
                "pre_ip": "216.239.57.99",
                "action": "C",
                "actiondate": "2004-05-08",
                "action_in_words": "Change",
            },
        ],
    }
}


def test_get_reverse_domain_action_success():
    action = DomaintoolsReverseDomain()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        # Mock the actual URL that will be called (including domain parameter)
        mock_requests.get(urllib.parse.urljoin(HOST, URI), json=DT_OUTPUT)  # Return the expected response
        result = action.run({"domain": DOMAIN})

        assert result is not None
        data = result  # Response is already a dict, no need for json.loads()

        assert data["domain_name"] == "google.com"
        assert len(data["ip_history"]) == 2
        assert data["ip_history"][0]["domain"] == "GOOGLE.COM"
        assert data["ip_history"][0]["post_ip"] == "216.239.57.99"
        assert data["ip_history"][0]["action"] == "N"
        assert data["ip_history"][1]["post_ip"] == "66.102.7.99"
        assert data["ip_history"][1]["pre_ip"] == "216.239.57.99"
        assert data["ip_history"][1]["action"] == "C"
        assert mock_requests.call_count == 1


def test_get_reverse_domain_action_api_error():
    action = DomaintoolsReverseDomain()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            status_code=500,  # Return an error status
            json={"error": {"message": "Internal Server Error"}},
        )
        result = action.run({"domain": DOMAIN})

        if result:
            data = result  # Response is already a dict, no need for json.loads()
            assert "error" in data or "Error" in str(data)
        else:
            assert not result

        assert mock_requests.call_count == 1
