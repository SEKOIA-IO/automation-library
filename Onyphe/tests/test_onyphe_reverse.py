import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_reverse import OnypheReverseAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheReverseAction


@pytest.fixture
def ressource():
    return "reverse/211.72.19.210"


@pytest.fixture
def bad_ressource():
    return "reverse/8.8.8"


@pytest.fixture
def arguments():
    return {"ip": "211.72.19.210"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"ip": "8.8.8"}),
        (InvalidArgument, {"ip": 8}),
        (TypeError, {}),
    ]


reverse_result = {
    "count": 1,
    "error": 0,
    "max_page": 1,
    "myip": "<redacted>",
    "page": 1,
    "results": [
        {
            "@category": "resolver",
            "@timestamp": "2018-10-26T12:28:18.000Z",
            "@type": "doc",
            "asn": "AS3462",
            "city": "Taipei",
            "country": "TW",
            "domain": "hinet.net",
            "host": "211-72-19-210",
            "ip": "211.72.19.210",
            "ipv6": "false",
            "location": "25.0478,121.5318",
            "organization": "Data Communication Business Group",
            "reverse": "211-72-19-210.hinet-ip.hinet.net",
            "seen_date": "2018-10-26",
            "source": "resolver",
            "subdomains": ["hinet-ip.hinet.net"],
            "subnet": "211.72.0.0/16",
            "tld": "net",
            "type": "reverse",
        }
    ],
    "status": "ok",
    "took": "0.026",
    "total": 1,
}


@pytest.fixture
def result():
    return reverse_result


@pytest.fixture
def result_page_0():
    return reverse_result


@pytest.fixture
def result_page_1():
    return {}
