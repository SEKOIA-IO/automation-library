import pytest
from pydantic import ValidationError
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_sniffer import OnypheSnifferAction


@pytest.fixture
def OnypheAction():
    return OnypheSnifferAction


@pytest.fixture
def ressource():
    return "sniffer/217.138.28.194"


@pytest.fixture
def bad_ressource():
    return "sniffer/8.8.8"


@pytest.fixture
def arguments():
    return {"ip": "217.138.28.194"}


@pytest.fixture
def bad_arguments():
    return [
        (ValidationError, {"ip": "8.8.8"}),
        (ValidationError, {"ip": 8}),
        (ValidationError, {}),
        (ValidationError, {"ip": "217.138.28.194", "budget": -1}),
        (ValidationError, {"ip": "217.138.28.194", "first_page": 0}),
    ]


sniffer_result = {
    "count": 1,
    "error": 0,
    "max_page": 1,
    "myip": "<redacted>",
    "page": 1,
    "results": [
        {
            "@category": "sniffer",
            "@timestamp": "2018-11-01T12:20:53.000Z",
            "@type": "doc",
            "asn": "AS20952",
            "city": "London",
            "country": "GB",
            "data": "\\x0e\\xc2\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00 "
            "CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\\x00\\x00!\\x00\\x01",
            "datamd5": "a5cc89fe2f131f33759daf33d1906649",
            "destport": "137",
            "ip": "217.138.28.194",
            "ipv6": "false",
            "location": "51.5085,-0.1257",
            "organization": "Venus Business Communications Limited",
            "seen_date": "2018-11-01",
            "srcport": "137",
            "subnet": "217.138.0.0/16",
            "tag": ["netbiosns", "udpdata"],
            "transport": "udp",
            "type": "udpdata",
        }
    ],
    "status": "ok",
    "took": "0.049",
    "total": 30,
}


@pytest.fixture
def result():
    return sniffer_result


@pytest.fixture
def result_page_0():
    return sniffer_result


@pytest.fixture
def result_page_1():
    return {}
