from typing import Any, Dict
import requests_mock
import json

from domaintools.get_reverse_ip import DomaintoolsReverseIP

import datetime
import urllib.parse
import hmac
import hashlib

IP_ADDRESS: str = "23.192.228.80"
HOST = "https://api.domaintools.com/"
URI = f"v1/{IP_ADDRESS}/reverse-ip/"
API_KEY = "LOREM"
API_USERNAME = "IPSUM"
TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(api_username, api_key, timestamp, uri):
    params = "".join([api_username, timestamp, uri])
    return hmac.new(api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1).hexdigest()


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
                    "abcai.eu",
                ],
            }
        ]
    }
}


def test_get_reverse_ip_action_success():
    action = DomaintoolsReverseIP()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        # Mock the actual URL that will be called (including IP in URL path)
        # /!\ IP is not sent in params but in the URL path /!\
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            json=DT_OUTPUT,  # Return the expected response
        )
        result = action.run({"ip": IP_ADDRESS})

        assert result is not None
        data = result  # Response is already a dict, no need for json.loads()

        assert len(data["ip_addresses"]) == 1
        assert data["ip_addresses"][0]["ip_address"] == "23.192.228.80"
        assert data["ip_addresses"][0]["domain_count"] == 162
        assert len(data["ip_addresses"][0]["domain_names"]) == 17
        assert "0x1bf52.top" in data["ip_addresses"][0]["domain_names"]
        assert mock_requests.call_count == 1


def test_get_reverse_ip_action_api_error():
    action = DomaintoolsReverseIP()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            status_code=500,  # Return an error status
            json={"error": {"message": "Internal Server Error"}},
        )
        result = action.run({"ip": IP_ADDRESS})

        if result:
            data = result  # Response is already a dict, no need for json.loads()
            assert "error" in data or "Error" in str(data)
        else:
            assert not result

        assert mock_requests.call_count == 1
