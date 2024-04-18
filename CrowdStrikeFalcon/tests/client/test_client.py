import os

import pytest
import requests_mock
from requests.exceptions import HTTPError

from crowdstrike_falcon.client import CrowdstrikeFalconClient


def test_list_streams():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    client = CrowdstrikeFalconClient(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                    "pagination": {
                        "limit": 100,
                        "offset": "1658342945857000000:3867296750",
                    },
                },
                "resources": [{"dataFeedURL": "stream?q=1"}],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2"
            "?appId=sio-00000&offset=1658342945857000000:3867296750",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [{"dataFeedURL": "stream?q=2"}],
            },
        )

        streams = client.list_streams("sio-00000")
        assert list(streams) == [
            {"dataFeedURL": "stream?q=1"},
            {"dataFeedURL": "stream?q=2"},
        ]


def test_list_streams_return_an_error():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    client = CrowdstrikeFalconClient(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [{"code": 404, "message": "stream2 - Resource Not Found"}],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                    "pagination": {
                        "limit": 100,
                        "offset": "1658342945857000000:3867296750",
                    },
                },
                "resources": [{"dataFeedURL": "stream?q=1"}],
            },
        )

        with pytest.raises(HTTPError):
            list(client.list_streams("sio-00000"))


def test_list_streams_empty():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    client = CrowdstrikeFalconClient(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": None,
            },
        )

        streams = client.list_streams("sio-00000")
        assert list(streams) == []


@pytest.mark.skipif(
    "{'CROWDSTRIKE_CLIENT_ID', 'CROWDSTRIKE_CLIENT_SECRET', 'CROWDSTRIKE_BASE_URL'}"
    ".issubset(os.environ.keys()) == False"
)
def test_list_streams_integration():
    client = CrowdstrikeFalconClient(
        os.environ["CROWDSTRIKE_BASE_URL"],
        os.environ["CROWDSTRIKE_CLIENT_ID"],
        os.environ["CROWDSTRIKE_CLIENT_SECRET"],
    )
    streams = client.list_streams("sio-integration-{time.time()}")
    assert len(list(streams)) > 0


def test_find_indicators():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    client = CrowdstrikeFalconClient(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/iocs/queries/indicators/v1?filter=source%3ASekoia.io",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "56d6393d-91c9-4df1-9767-9498c013e620",
                    "pagination": {
                        "limit": 100,
                        "total": 1,
                        "offset": "1658342945857000000:3867296750",
                        "after": "ZDI2ZWMxZmUtODg2NS00MWUzLWJiMWItZDQxMzU3NGI3ZmFh",
                    },
                },
                "resources": ["519b7236-8ed2-4c63-b5c4-0f72dc3f187e"],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/iocs/queries/indicators/v1"
            "?filter=source%3ASekoia.io&after=ZDI2ZWMxZmUtODg2NS00MWUzLWJiMWItZDQxMzU3NGI3ZmFh",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": ["f6d85700-1b5b-450f-8df1-a8317fe7f137"],
            },
        )

        indicators = client.find_indicators(fql_filter=f"source:Sekoia.io")
        assert list(indicators) == ["519b7236-8ed2-4c63-b5c4-0f72dc3f187e", "f6d85700-1b5b-450f-8df1-a8317fe7f137"]
