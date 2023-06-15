import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_synscan import OnypheSynscanAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheSynscanAction


@pytest.fixture
def ressource():
    return "synscan/93.184.216.34"


@pytest.fixture
def bad_ressource():
    return "synscan/8.8.8"


@pytest.fixture
def arguments():
    return {"ip": "93.184.216.34"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"ip": "8.8.8"}),
        (InvalidArgument, {"ip": 8}),
        (TypeError, {}),
    ]


synscan_result = {
    "count": 2,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [
        {
            "@category": "synscan",
            "@timestamp": "2019-09-14T20:49:27.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "os": "Unknown",
            "port": "80",
            "seen_date": "2019-09-14",
            "source": "synscan",
            "subnet": "93.184.216.34/32",
        },
        {
            "@category": "synscan",
            "@timestamp": "2019-09-12T13:40:44.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "os": "Unknown",
            "port": "443",
            "seen_date": "2019-09-12",
            "source": "synscan",
            "subnet": "93.184.216.34/32",
        },
    ],
    "status": "ok",
    "took": "0.032",
    "total": 2,
}


@pytest.fixture
def result():
    return synscan_result


@pytest.fixture
def result_page_0():
    return synscan_result


@pytest.fixture
def result_page_1():
    return {}
