from typing import Any, Dict
import requests_mock

from domaintools.get_iris_reverse_ip import DomaintoolsIrisReverseIP

import datetime
import urllib.parse
import hmac
import hashlib

IP_ADDRESS: str = "199.30.228.112"
HOST = "https://api.domaintools.com/"
URI = "v1/iris-investigate/"
API_KEY = "LOREM"
API_USERNAME = "IPSUM"
TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(api_username, api_key, timestamp, uri):
    params = "".join([api_username, timestamp, uri])
    return hmac.new(api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1).hexdigest()


signature = sign(API_USERNAME, API_KEY, TIMESTAMP, URI)

DT_OUTPUT: dict[str, Any] = {
    "response": {
        "limit_exceeded": False,
        "has_more_results": False,
        "message": "Enjoy your data.",
        "results_count": 1,
        "total_count": 1,
        "results": [
            {
                "domain": "lemonde.fr",
                "whois_url": "https://whois.domaintools.com/lemonde.fr",
                "active": True,
                "popularity_rank": 1386,
                "domain_risk": {"risk_score": 4, "components": [{"name": "proximity", "risk_score": 4}]},
                "registrar": {"value": "NAMESHIELD", "count": 72661},
                "registrant_name": {"value": "SOCIETE EDITRICE du monde", "count": 119},
                "create_date": {"value": "2005-08-02", "count": 26351},
                "expiration_date": {"value": "2026-06-09", "count": 818191},
                "ip": [
                    {
                        "address": {"value": "151.101.122.137", "count": 1},
                        "asn": [{"value": 54113, "count": 1660827}],
                        "country_code": {"value": "us", "count": 190148996},
                        "isp": {"value": "Fastly Inc.", "count": 612736},
                    }
                ],
                "tld": "fr",
                "website_response": 200,
                "website_title": {
                    "value": "Le Monde.fr - Actualités et Infos en France et dans le monde",
                    "count": 407,
                },
                "server_type": {"value": "fasthttp", "count": 3195},
                "first_seen": {"value": "2023-01-26T17:57:05Z", "count": 0},
            }
        ],
        "missing_domains": [],
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


def test_get_iris_reverse_ip_action_success():
    action = DomaintoolsIrisReverseIP()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            json=DT_OUTPUT,
            additional_matcher=_qs_matcher({"ip": IP_ADDRESS}),
        )
        result = action.run({"ip": IP_ADDRESS})

        assert result is not None
        data = result

        assert data["results_count"] == 1
        assert data["total_count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["domain"] == "lemonde.fr"
        assert data["results"][0]["domain_risk"]["risk_score"] == 4
        assert data["results"][0]["active"] is True
        assert data["results"][0]["tld"] == "fr"
        assert data["results"][0]["website_response"] == 200
        assert mock_requests.call_count == 1


def test_get_iris_reverse_ip_action_api_error():
    action = DomaintoolsIrisReverseIP()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"ip": IP_ADDRESS}),
        )
        result = action.run({"ip": IP_ADDRESS})

        if result:
            data = result
            assert "error" in data or "Error" in str(data)
        else:
            assert not result

        assert mock_requests.call_count == 1


def test_get_iris_reverse_ip_action_multiple_results():
    """Test handling of multiple domain results"""
    action = DomaintoolsIrisReverseIP()
    action.module.configuration = {"api_key": API_KEY, "api_username": API_USERNAME, "host": HOST}

    multi_result_output = {
        "response": {
            "limit_exceeded": False,
            "has_more_results": True,
            "message": "Enjoy your data.",
            "results_count": 2,
            "total_count": 150,
            "results": [
                {"domain": "example1.com", "domain_risk": {"risk_score": 10}, "active": True},
                {"domain": "example2.com", "domain_risk": {"risk_score": 85}, "active": False},
            ],
            "missing_domains": [],
        }
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, URI),
            json=multi_result_output,
            additional_matcher=_qs_matcher({"ip": IP_ADDRESS}),
        )
        result = action.run({"ip": IP_ADDRESS})

        assert result is not None
        assert result["results_count"] == 2
        assert result["total_count"] == 150
        assert result["has_more_results"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["domain"] == "example1.com"
        assert result["results"][1]["domain"] == "example2.com"
        assert result["results"][1]["domain_risk"]["risk_score"] == 85
