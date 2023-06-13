import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_onionscan import OnypheOnionscanAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheOnionscanAction


@pytest.fixture
def ressource():
    return "onionscan/mh7mkfvezts5j6yu.onion"


@pytest.fixture
def bad_ressource():
    return "onionscan/examplecom"


@pytest.fixture
def arguments():
    return {"onion": "MH7MKFVEZTS5J6YU.ONION"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"onion": 33}),
        (InvalidArgument, {"onion": "examplecom.onion"}),
        (TypeError, {}),
    ]


onionscan_result = {
    "count": 1,
    "error": 0,
    "max_page": 1,
    "myip": "<redacted>",
    "page": 1,
    "results": [
        {
            "@category": "onionscan",
            "@timestamp": "2018-10-24T19:03:31.000Z",
            "@type": "doc",
            "app": {
                "extract": {
                    "domain": [
                        "wikipedia.org",
                        "wikibooks.org",
                        "haskell.org",
                        "ats-lang.org",
                    ],
                    "file": ["grdt-popl03.pdf"],
                    "hostname": [
                        "en.wikibooks.org",
                        "en.wikipedia.org",
                        "wiki.haskell.org",
                        "www.ats-lang.org",
                    ],
                    "url": [
                        "http://www.ats-lang.org/MYDATA/GRDT-popl03.pdf",
                        "http://www.ats-lang.org/",
                        "https://en.wikibooks.org/wiki/Haskell/GADT",
                        "https://wiki.haskell.org/GADTs_for_dummies",
                        "https://en.wikipedia.org/wiki/Generalized_algebraic_data_type",
                    ],
                },
                "http": {
                    "bodymd5": "d41d8cd98f00b204e9800998ecf8427e",
                    "headermd5": "297ee2062d5eab6d7a30bd8656730536",
                    "title": "Bluish Coder",
                },
                "length": "4096",
            },
            "cpe": ["cpe:/a:igor_sysoev:nginx:1.10.3"],
            "data": 'HTTP/1.1 200 OK\r\nContent-Length: 93915\r\nETag: "5bc71236-16edb"\r\nDate: Wed, 24 Oct 2018...',
            "datamd5": "6f50408650910af16c5f8b229202264e",
            "device": {"class": "Web Server"},
            "domain": "mh7mkfvezts5j6yu.onion",
            "hostname": "mh7mkfvezts5j6yu.onion",
            "onion": "mh7mkfvezts5j6yu.onion",
            "os": "Linux",
            "osdistribution": "Ubuntu",
            "port": 80,
            "product": "Nginx",
            "productvendor": "Igor Sysoev",
            "productversion": "1.10.3",
            "protocol": "http",
            "protocolversion": "1.1",
            "reason": "OK",
            "seen_date": "2018-10-24",
            "source": "datascan",
            "status": "200",
            "tag": ["ok"],
            "tls": "false",
            "url": "/",
        }
    ],
    "status": "ok",
    "took": "0.004",
    "total": 2,
}


@pytest.fixture
def result():
    return onionscan_result


@pytest.fixture
def result_page_0():
    return onionscan_result


@pytest.fixture
def result_page_1():
    return {}
