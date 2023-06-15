import pytest
import requests_mock
from requests.exceptions import HTTPError

from onyphe.action_onyphe_geoloc import OnypheGeolocAction as OnypheAction
from onyphe.errors import InvalidArgument

base_url = "https://www.onyphe.io/api/v2/simple/geoloc/"


action_result: dict = {
    "count": 1,
    "error": 0,
    "myip": "185.122.161.248",
    "results": [
        {
            "@category": "geoloc",
            "@timestamp": "2019-09-12T13:44:33.000Z",
            "@type": "doc",
            "asn": "AS3356",
            "city": "",
            "country": "US",
            "ip": "8.8.8.8",
            "ipv6": "false",
            "latitude": "37.7510",
            "location": "37.7510,-97.8220",
            "longitude": "-97.8220",
            "organization": "Level 3 Parent, LLC",
            "subnet": "8.8.0.0/17",
        }
    ],
    "status": "ok",
    "took": "0.004",
    "total": 1,
}


action_result_ipv6 = {
    "count": 1,
    "error": 0,
    "myip": "185.122.161.248",
    "results": [
        {
            "@category": "geoloc",
            "@timestamp": "2019-09-16T15:35:55.000Z",
            "@type": "doc",
            "asn": "AS15169",
            "city": "",
            "country": "US",
            "ip": "2001:4860:4860::8888",
            "ipv6": "true",
            "latitude": "37.7510",
            "location": "37.7510,-97.8220",
            "longitude": "-97.8220",
            "organization": "Google LLC",
            "subnet": "2001:4860:4800::/37",
        }
    ],
    "status": "ok",
    "took": "0.004",
    "total": 1,
}


def test_onyphe_geoloc_success():
    action: OnypheAction = OnypheAction()

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}8.8.8.8", json=action_result)
        mock.get(f"{base_url}2001:4860:4860::8888", json=action_result_ipv6)

        results: dict = action.run({"ip": "8.8.8.8"})
        assert results == action_result

        results: dict = action.run({"ip": "2001:4860:4860::8888"})
        assert results == action_result_ipv6

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}8.8.8.8"
        assert history[1].method == "GET"
        assert history[1].url == f"{base_url}2001:4860:4860::8888"


def test_onyphe_geoloc_invalidIP():
    action: OnypheAction = OnypheAction()

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}8.8.8", json={}, status_code=404, reason="Not Found")

        pytest.raises(InvalidArgument, action.run, {"ip": "8.8.8"})

        assert mock.call_count == 0

        pytest.raises(InvalidArgument, action.run, {"ip": 8})

        assert mock.call_count == 0

        pytest.raises(TypeError, action.run, {})

        assert mock.call_count == 0


def test_onyphe_geoloc_quota():
    action: OnypheAction = OnypheAction()

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}8.8.8.8",
            json={"error": 20, "message": "rate limit reached", "status": "nok"},
            status_code=429,
            reason="Too Many Requests",
        )

        pytest.raises(HTTPError, action.run, {"ip": "8.8.8.8"})

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}8.8.8.8"
