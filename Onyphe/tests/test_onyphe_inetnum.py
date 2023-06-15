import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_inetnum import OnypheInetnumAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheInetnumAction


@pytest.fixture
def ressource():
    return "inetnum/93.184.216.34"


@pytest.fixture
def bad_ressource():
    return "inetnum/8.8.8"


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


inetnum_result = {
    "count": 3,
    "error": 0,
    "myip": "185.122.161.248",
    "results": [
        {
            "@category": "inetnum",
            "@timestamp": "2019-09-15T01:41:09.000Z",
            "@type": "doc",
            "country": "US",
            "ipv6": "false",
            "subnet": "93.184.208.0/20",
            "netname": "EU-EDGECASTEU-20080602",
            "seen_date": "2019-09-15",
            "source": "RIPE",
        },
        {
            "@category": "inetnum",
            "@timestamp": "2019-09-15T01:41:09.000Z",
            "@type": "doc",
            "country": "EU",
            "information": ["NETBLK-03-EU-93-184-216-0-24"],
            "netname": "EDGECAST-NETBLK-03",
            "seen_date": "2019-09-15",
            "source": "RIPE",
            "subnet": "93.184.216.0/24",
            "ipv6": "false",
        },
        {
            "@category": "inetnum",
            "@timestamp": "2019-09-08T01:40:22.000Z",
            "@type": "doc",
            "seen_date": "2019-09-08",
            "source": "RIPE",
            "country": "US",
            "ipv6": "false",
            "netname": "EU-EDGECASTEU-20080602",
            "subnet": "93.184.208.0/20",
        },
    ],
    "status": "ok",
    "took": "0.814",
    "total": 3,
    "max_page": 1,
    "page": 1,
}


@pytest.fixture
def result():
    return inetnum_result


@pytest.fixture
def result_page_0():
    return inetnum_result


@pytest.fixture
def result_page_1():
    return {}
