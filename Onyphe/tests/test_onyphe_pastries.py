import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_pastries import OnyphePastriesAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnyphePastriesAction


@pytest.fixture
def ressource():
    return "pastries/93.184.216.34"


@pytest.fixture
def bad_ressource():
    return "pastries/8.8.8"


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


pastries_result = {
    "count": 3,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [
        {
            "@category": "pastries",
            "@timestamp": "2019-09-16T14:20:37.000Z",
            "@type": "doc",
            "seen_date": "2019-09-16",
            "source": "pastebin",
            "domain": ["example.com"],
            "file": ["client.py", "certmonger.py"],
            "hostname": ["ldap-vx-010101-1.foo.example.com"],
            "ip": ["2606:2800:220:1:248:1893:25c8:1946", "93.184.216.34"],
            "key": "LdvbAZJU",
            "scheme": ["https"],
            "size": "856",
            "syntax": "text",
            "tld": "com",
            "url": ["https://ldap-vx-010101-1.foo.example.com/ipa/xml"],
        },
        {
            "@category": "pastries",
            "@timestamp": "2019-09-16T13:31:00.000Z",
            "@type": "doc",
            "seen_date": "2019-09-16",
            "source": "pastebin",
            "domain": ["example.com"],
            "hostname": ["admin.example.com"],
            "ip": ["2606:2800:220:1:248:1893:25c8:1946", "93.184.216.34"],
            "key": "dKRhrGzN",
            "scheme": ["http"],
            "size": "606",
            "syntax": "html4strict",
            "title": "Security1",
            "tld": "com",
            "url": ["http://admin.example.com/delete-user/123456"],
            "user": "AlekseyNaydenko",
        },
        {
            "@category": "pastries",
            "@timestamp": "2019-09-16T12:47:47.000Z",
            "@type": "doc",
            "seen_date": "2019-09-16",
            "source": "pastebin",
            "domain": ["google.com", "github.com", "1e100.net", "example.com"],
            "file": ["feed.xml", "requirements.txt"],
            "host": [
                "wl-in-f93",
                "dl",
                "par21s04-in-f174",
                "wl-in-f91",
                "par10s28-in-f14",
                "par21s17-in-x0e",
                "par21s04-in-f14",
                "ams15s33-in-x0e",
                "dl-ssl",
                "wa-in-xbe",
                "par10s28-in-f110",
                "lb-140-82-118-3-ams",
                "wl-in-f190",
                "wl-in-f136",
            ],
            "hostname": [
                "wl-in-f91.1e100.net",
                "par21s17-in-x0e.1e100.net",
                "dl.google.com",
                "wl-in-f93.1e100.net",
                "dl-ssl.google.com",
                "par21s04-in-f14.1e100.net",
                "lb-140-82-118-3-ams.github.com",
                "par21s04-in-f174.1e100.net",
                "par10s28-in-f14.1e100.net",
                "ams15s33-in-x0e.1e100.net",
                "par10s28-in-f110.1e100.net",
                "wl-in-f136.1e100.net",
                "wl-in-f190.1e100.net",
                "wa-in-xbe.1e100.net",
            ],
            "ip": [
                "64.233.167.136",
                "2606:2800:220:1:248:1893:25c8:1946",
                "140.82.118.3",
                "216.58.213.174",
                "93.184.216.34",
                "64.233.167.91",
                "216.58.204.110",
                "2a00:1450:400e:80a:0:0:0:200e",
                "2a00:1450:400c:c0b:0:0:0:be",
                "64.233.167.93",
                "2a00:1450:4007:808:0:0:0:200e",
                "64.233.167.190",
            ],
            "key": "kSK4SRTX",
            "scheme": ["http", "https"],
            "size": "3144",
            "syntax": "text",
            "tld": ["com", "net"],
            "url": [
                "https://dl-ssl.google.com/linux/linux_signing_key.pub",
                "https://github.com/pirate/ArchiveBox",
                "https://example.com/some/rss/feed.xml",
                "http://dl.google.com/linux/chrome/deb/",
                "https://example.com",
                "https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64",
                "https://github.com/pirate/ArchiveBox/wiki/Docker",
            ],
        },
    ],
    "status": "ok",
    "took": "0.058",
    "total": 238,
}


@pytest.fixture
def result():
    return pastries_result


@pytest.fixture
def result_page_0():
    return pastries_result


@pytest.fixture
def result_page_1():
    return {}
