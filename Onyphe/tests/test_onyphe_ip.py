import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_ip import OnypheIpAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheIpAction


@pytest.fixture
def ressource():
    return "ip/8.8.8.8"


@pytest.fixture
def bad_ressource():
    return "ip/8.8.8"


@pytest.fixture
def arguments():
    return {"ip": "8.8.8.8"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"ip": "8.8.8"}),
        (InvalidArgument, {"ip": 8}),
        (TypeError, {}),
    ]


ip_result = [
    {
        "@category": "ip",
        "@timestamp": "2019-09-13T13:58:10.000Z",
        "@type": "doc",
        "asn": "AS15133",
        "city": "Norwell",
        "country": "US",
        "ip": "93.184.216.34",
        "ipv6": "false",
        "latitude": "42.1596",
        "location": "42.1596,-70.8217",
        "longitude": "-70.8217",
        "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
        "subnet": "93.184.216.34/32",
    },
    {
        "@category": "inetnum",
        "@timestamp": "2019-09-08T01:40:22.000Z",
        "@type": "doc",
        "country": "EU",
        "information": ["NETBLK-03-EU-93-184-216-0-24"],
        "netname": "EDGECAST-NETBLK-03",
        "seen_date": "2019-09-08",
        "source": "RIPE",
        "subnet": "93.184.216.0/24",
    },
    {
        "@category": "pastries",
        "@timestamp": "2019-09-13T13:52:17.000Z",
        "@type": "doc",
        "domain": ["example.com"],
        "key": "Te5D0eeu",
        "seen_date": "2019-09-13",
        "size": "320",
        "source": "pastebin",
        "syntax": "javascript",
        "url": ["https://example.com"],
    },
    {
        "@category": "pastries",
        "@timestamp": "2019-09-13T12:46:46.000Z",
        "@type": "doc",
        "domain": ["example.com"],
        "key": "aFkYHLBX",
        "seen_date": "2019-09-13",
        "size": "766",
        "source": "pastebin",
        "syntax": "php",
        "url": ["https://example.com"],
    },
    {
        "@category": "pastries",
        "@timestamp": "2019-09-13T11:44:11.000Z",
        "@type": "doc",
        "domain": ["example.com"],
        "key": "7p3GG1fE",
        "seen_date": "2019-09-13",
        "size": "4334",
        "source": "pastebin",
        "syntax": "javascript",
        "url": ["https://example.com/"],
    },
    {
        "@category": "pastries",
        "@timestamp": "2019-09-13T05:41:34.000Z",
        "@type": "doc",
        "domain": ["example.com", "drupal.org"],
        "hostname": ["www.example.com", "www.drupal.org"],
        "key": "q6FJ0fnX",
        "seen_date": "2019-09-13",
        "size": "4657",
        "source": "pastebin",
        "syntax": "text",
        "url": [
            "http://www.example.com/",
            "http://example.com/",
            "http://www.example.com/foo",
            "https://www.drupal.org/node/2783079.",
            "http://example.com/foo",
        ],
    },
]


@pytest.fixture
def result():
    return {
        "count": 6,
        "error": 0,
        "myip": "185.122.161.248",
        "results": ip_result[0:6],
        "status": "ok",
        "took": "0.814",
        "total": 752,
        "max_page": 100,
        "page": 2,
    }


@pytest.fixture
def result_page_0():
    return {
        "count": 2,
        "error": 0,
        "myip": "185.122.161.248",
        "results": ip_result[0:2],
        "status": "ok",
        "took": "0.414",
        "total": 752,
        "max_page": 100,
        "page": 1,
    }


@pytest.fixture
def result_page_1():
    return {
        "count": 4,
        "error": 0,
        "myip": "185.122.161.248",
        "results": ip_result[2:6],
        "status": "ok",
        "took": "0.400",
        "total": 752,
        "max_page": 100,
        "page": 2,
    }
