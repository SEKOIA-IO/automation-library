import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_datascan import OnypheDatascanAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheDatascanAction


@pytest.fixture
def ressource():
    return "datascan/example"


@pytest.fixture
def bad_ressource():
    return "datascan/8.8.8"


@pytest.fixture
def arguments():
    return {"string": "example"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"ip": "8.8.8"}),
        (InvalidArgument, {"ip": 8}),
        (TypeError, {}),
        (TypeError, {"ip": "93.184.216.34", "string": "example"}),
    ]


datascan_result = {
    "count": 2,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [
        {
            "@category": "datascan",
            "@timestamp": "2019-09-17T09:29:06.000Z",
            "@type": "doc",
            "seen_date": "2019-09-17",
            "source": "datascan",
            "domain": "googleusercontent.com",
            "hostname": ["91.121.241.35.bc.googleusercontent.com"],
            "ip": "35.241.121.91",
            "url": "/",
            "asn": "AS15169",
            "data": "HTTP/1.1 403 Forbidden\r\nDate: Tue, 17 Sep 2019 09:28:57 GMT\r\nServer: Apache/2.4.6 (CentO...",
            "datamd5": "892ceae050b787f8f4e42488c7a7d67b",
            "ipv6": "false",
            "location": "35.0000,105.0000",
            "organization": "Google LLC",
            "port": "80",
            "protocol": "http",
            "protocolversion": "1.1",
            "reason": "Forbidden",
            "status": "403",
            "subnet": "35.241.64.0/18",
            "tls": "false",
            "transport": "tcp",
            "host": "91",
            "os": "Linux",
            "osdistribution": "CentOS",
            "osvendor": "Linux",
            "product": "HTTP Server",
            "productvendor": "Apache",
            "productversion": "2.4.6",
            "reverse": "91.121.241.35.bc.googleusercontent.com",
            "subdomains": [
                "121.241.35.bc.googleusercontent.com",
                "241.35.bc.googleusercontent.com",
                "35.bc.googleusercontent.com",
                "bc.googleusercontent.com",
            ],
            "tld": "com",
        },
        {
            "@category": "datascan",
            "@timestamp": "2019-09-17T09:29:06.000Z",
            "@type": "doc",
            "seen_date": "2019-09-17",
            "source": "datascan",
            "domain": ["elinkstaging.com"],
            "hostname": ["pkg.elinkstaging.com"],
            "ip": "64.191.166.46",
            "url": "/",
            "asn": "AS13776",
            "city": "Lexington",
            "country": "US",
            "data": "HTTP/1.1 403 Forbidden\r\nDate: Tue, 17 Sep 2019 09:29:00 GMT\r\nServer: Apache/2.2.15 (Cent...",
            "datamd5": "69761b9b9ecee1852e366861ad937e1f",
            "ipv6": "false",
            "location": "38.0464,-84.4953",
            "organization": "QX.Net",
            "port": "443",
            "protocol": "http",
            "protocolversion": "1.1",
            "reason": "Forbidden",
            "status": "403",
            "subnet": "64.191.164.0/22",
            "tls": "true",
            "transport": "tcp",
            "basicconstraints": "critical",
            "ca": "false",
            "extkeyusage": ["serverAuth", "clientAuth"],
            "fingerprint": {
                "md5": "aa308ed5d930134c97607bd58fe2c4e2",
                "sha1": "994c3fba15b742b6e7bcd4cca15d35747e214c6f",
                "sha256": "fc7e3dc3f158e86e2670f3037221dba373558f7fa36cc0be307a0fbdb684088c",
            },
            "host": ["pkg"],
            "issuer": {
                "commonname": "Let's Encrypt Authority X3",
                "country": "US",
                "organization": "Let's Encrypt",
            },
            "keyusage": ["digitalSignature", "keyEncipherment"],
            "os": "Linux",
            "osdistribution": "CentOS",
            "osvendor": "Linux",
            "product": "HTTP Server",
            "productvendor": "Apache",
            "productversion": "2.2.15",
            "publickey": {"algorithm": "rsaEncryption", "length": "2048"},
            "serial": "04:56:85:8a:63:88:6e:91:4c:1d:5c:c6:6b:5c:8f:3e:ec:e6",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {
                "altname": ["pkg.elinkstaging.com"],
                "commonname": "pkg.elinkstaging.com",
            },
            "tld": ["com"],
            "validity": {
                "notafter": "2019-11-03T11:41:24Z",
                "notbefore": "2019-08-05T11:41:24Z",
            },
            "version": "v3",
            "wildcard": "false",
        },
    ],
    "status": "ok",
    "took": "0.410",
    "total": 7177746,
}


@pytest.fixture
def result():
    return datascan_result


@pytest.fixture
def result_page_0():
    return datascan_result


@pytest.fixture
def result_page_1():
    return {}
