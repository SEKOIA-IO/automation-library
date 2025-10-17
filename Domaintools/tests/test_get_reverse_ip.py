from typing import Any, Dict
import requests_mock
import json

from domaintools.get_reverse_ip import DomaintoolsReverseIP

import datetime
import urllib.parse
import hmac
import hashlib

DOMAIN: str = "google.com"
HOST = "https://api.domaintools.com/"
#URI = f"v1/iris-investigate/"  # Base URI without domain
URI = f"v1/{DOMAIN}/reverse-ip/"
API_KEY = "LOREM"
API_USERNAME = "IPSUM"
TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sign(api_username, api_key, timestamp, uri):
    params = "".join([api_username, timestamp, uri])
    return hmac.new(
        api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1
    ).hexdigest()

signature = sign(API_USERNAME, API_KEY, TIMESTAMP, URI)

DT_OUTPUT: dict[str, Any] = {
  "response": {
    "ip_addresses": [
        {
        "ip_address": "23.192.228.80",
        "domain_count": 162,
        "domain_names": [
            "0x1bf52.top",
            "axxxxu.com",
            "peterboroughthunder.com",
            "getinsurtech.com",
            "wp1clickqa20-01also-a.one",
            "tim.monster",
            "reportly.io",
            "ourspacenz.com",
            "janikbruell.com",
            "skansk.com",
            "codeninjascerritos.com",
            "brianyao.com",
            "cnnvm.com",
            "framina.at",
            "mowuzzuf.com",
            "deadhand.games",
            "abcai.eu"]
        }]
    }
}

""" 
def _qs_matcher(expected_params: Dict[str, Any]):

    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        # Check that all expected params are present with correct values
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher
 """

def test_get_reverse_ip_action_success():
    action = DomaintoolsReverseIP()
    action.module.configuration = {
        "api_key": API_KEY,
        "api_username": API_USERNAME,
        "host": HOST
    }

    with requests_mock.Mocker() as mock_requests:
        # Mock the actual URL that will be called (including domain parameter)
        # /!\ DOMAIN is not sent in params but in the URL path /!\
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            json=DT_OUTPUT,  # Return the expected response
        )
        result = action.run({"domain": DOMAIN})

        assert result is not None
        
        # Parse the result - it might be nested in a wrapper
        data = json.loads(result)
        
        # Debug: print the actual structure
        print("Result structure:", json.dumps(data, indent=2))
        
        assert data["ip_addresses"] is not None
        assert mock_requests.call_count == 1


def test_get_reverse_ip_action_api_error():
    action = DomaintoolsReverseIP()
    action.module.configuration = {
        "api_key": API_KEY,
        "api_username": API_USERNAME,
        "host": HOST
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            status_code=500,  # Return an error status
            json={"error": {"message": "Internal Server Error"}}
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