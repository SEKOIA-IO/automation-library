import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_forward import OnypheForwardAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheForwardAction


@pytest.fixture
def ressource():
    return "forward/93.184.216.34"


@pytest.fixture
def bad_ressource():
    return "forward/8.8.8"


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


forward_result = {
    "count": 10,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:36:44.000Z",
            "@type": "doc",
            "seen_date": "2019-09-17",
            "source": "datascan",
            "domain": "example.com",
            "hostname": "www.example.com",
            "ip": "93.184.216.34",
            "asn": "AS15133",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "subnet": "93.184.216.34/32",
            "host": "www",
            "tld": "com",
            "city": "Norwell",
            "country": "US",
            "forward": "www.example.com",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:36:08.000Z",
            "@type": "doc",
            "seen_date": "2019-09-17",
            "source": "datascan",
            "domain": "example.com",
            "hostname": "example.com",
            "ip": "93.184.216.34",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "subnet": "93.184.216.34/32",
            "tld": "com",
            "forward": "example.com",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:21.000Z",
            "@type": "doc",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "domain": "example.net",
            "hostname": "example.net",
            "ip": "93.184.216.34",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "subnet": "93.184.216.34/32",
            "tld": "net",
            "forward": "example.net",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:21.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "domain": "example.edu",
            "hostname": "example.edu",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "subnet": "93.184.216.34/32",
            "tld": "edu",
            "forward": "example.edu",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:20.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "domain": "example.org",
            "forward": "example.org",
            "hostname": "example.org",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "subnet": "93.184.216.34/32",
            "tld": "org",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:20.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "country": "US",
            "domain": "example.edu",
            "hostname": "www.example.edu",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "subnet": "93.184.216.34/32",
            "host": "www",
            "tld": "edu",
            "city": "Norwell",
            "forward": "www.example.edu",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:20.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "domain": "example.net",
            "forward": "www.example.net",
            "hostname": "www.example.net",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "subnet": "93.184.216.34/32",
            "host": "www",
            "tld": "net",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T10:17:20.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "urlscan",
            "subnet": "93.184.216.34/32",
            "domain": "example.org",
            "forward": "www.example.org",
            "hostname": "www.example.org",
            "host": "www",
            "tld": "org",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T07:01:23.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "domain": "privymarketing.com",
            "hostname": "privymarketing.com",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "ctl",
            "subnet": "93.184.216.34/32",
            "tld": "com",
            "forward": "privymarketing.com",
            "type": "forward",
        },
        {
            "@category": "resolver",
            "@timestamp": "2019-09-17T07:01:22.000Z",
            "@type": "doc",
            "asn": "AS15133",
            "city": "Norwell",
            "country": "US",
            "domain": "privy-review.com",
            "hostname": "privy-review.com",
            "ip": "93.184.216.34",
            "ipv6": "false",
            "location": "42.1596,-70.8217",
            "organization": "MCI Communications Services, Inc. d/b/a Verizon Business",
            "seen_date": "2019-09-17",
            "source": "ctl",
            "subnet": "93.184.216.34/32",
            "tld": "com",
            "forward": "privy-review.com",
            "type": "forward",
        },
    ],
    "status": "ok",
    "took": "0.081",
    "total": 395,
}


@pytest.fixture
def result():
    return forward_result


@pytest.fixture
def result_page_0():
    return forward_result


@pytest.fixture
def result_page_1():
    return {}
