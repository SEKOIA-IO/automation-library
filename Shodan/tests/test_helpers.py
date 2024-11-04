import copy
import json
import os

import orjson
import pytest
import requests_mock
from shodan import GetShodanHost, GetShodanHostSearch
from shodan.helpers import sanitize_big_int, sanitize_node


def test_sanitize_big_int():
    assert sanitize_big_int(1234567890) == 1234567890
    assert sanitize_big_int(2899357035992737906989516748620396151) == "2899357035992737906989516748620396151"


def test_sanitize_node():
    # flake8: noqa
    result = {
        "ssl": {
            "cert": {
                "sig_alg": "sha256WithRSAEncryption",
                "issued": "20200626000000Z",
                "expires": "20220628120000Z",
                "pubkey": {"bits": 4096, "type": "rsa"},
                "version": 2,
                "extensions": [
                    {
                        "data": "0\\x16\\x80\\x14\\x90X\\xff\\xb0\\x9cu\\xa8QTw\\xb1\\xed\\xf2\\xa3C\\x168\\x9el\\xc5",
                        "name": "authorityKeyIdentifier",
                    },
                    {
                        "data": "\\x04\\x143R\\xf2\\xa1\\xd19p\\x86W\\x1a\\xea+\\x8b\\x04\\xeb\\xd2\\xa4\\x9c\\xe1g",
                        "name": "subjectKeyIdentifier",
                    },
                    {
                        "data": "0\\x16\\x82\\x14*.swat.outpost24.com",
                        "name": "subjectAltName",
                    },
                    {
                        "critical": True,
                        "data": "\\x03\\x02\\x05\\xa0",
                        "name": "keyUsage",
                    },
                    {
                        "data": "0\\x14\\x06\\x08+\\x06\\x01\\x05\\x05\\x07\\x03\\x01\\x06\\x08+\\x06\\x01\\x05\\x05\\x07\\x03\\x02",
                        "name": "extendedKeyUsage",
                    },
                    {
                        "data": "0503\\xa01\\xa0/\\x86-http://cdp.geotrust.com/GeoTrustRSACA2018.crl",
                        "name": "crlDistributionPoints",
                    },
                    {
                        "data": "0C07\\x06\\t`\\x86H\\x01\\x86\\xfdl\\x01\\x020*0(\\x06\\x08+\\x06\\x01\\x05\\x05\\x07\\x02\\x01\\x16\\x1chttps://www.digicert.com/CPS0\\x08\\x06\\x06g\\x81\\x0c\\x01\\x02\\x01",
                        "name": "certificatePolicies",
                    },
                    {
                        "data": "0g0&\\x06\\x08+\\x06\\x01\\x05\\x05\\x070\\x01\\x86\\x1ahttp://status.geotrust.com0=\\x06\\x08+\\x06\\x01\\x05\\x05\\x070\\x02\\x861http://cacerts.geotrust.com/GeoTrustRSACA2018.crt",
                        "name": "authorityInfoAccess",
                    },
                    {"data": "0\\x00", "name": "basicConstraints"},
                    {
                        "data": "\\x04\\x82\\x01j\\x01h\\x00v\\x00F\\xa5U\\xebu\\xfa\\x91 0\\xb5\\xa2\\x89i\\xf4\\xf3}\\x11,At\\xbe\\xfdI\\xb8\\x85\\xab\\xf2\\xfcp\\xfemG\\x00\\x00\\x01r\\xefR\\x0e\\xeb\\x00\\x00\\x04\\x03\\x00G0E\\x02 \\x02{?\\xa2!\\xe7(>j\\xaa\\xb8\\x87~\\x8b\\x8c\\x8c\\xcf\\xe4\\xc3o:-$I\\x14\\xbc }\\xa4\\x18\\x9f\\x00\\x02!\\x00\\x86(\\x80\\xa9\\xf2\\x84\\x8b\\xdfuZ\\xab&\\x10$\\xad\\x8b\\xf8n\\xb9\\xcc,D?-\\xae\\x17\\x90\\xf4\\xb0\\xb6\\xd2P\\x00w\\x00\"EE\\x07YU$V\\x96?\\xa1/\\xf1\\xf7m\\x86\\xe0#&c\\xad\\xc0K\\x7f]\\xc6\\x83\\\\n\\xe2\\x0f\\x02\\x00\\x00\\x01r\\xefR\\x0e\\xcc\\x00\\x00\\x04\\x03\\x00H0F\\x02!\\x00\\xf8\\xff\\nZ\\x10\\xb2\\xae\\xa0\\x06rur>\\x99u\\xfa\\xa2b\\xfa\\xf3\\xb4\\xfexj\\xd7%\\xb5\\x80\\x0c\\x8b\\'9\\x02!\\x00\\xd2F6\\xf8V1@5K\\xac3A\\x82\\x8dO5[\\xfa:`\\xb9.\\x99\\x18X1q\\x0e\\x1d\\x98\\xb2\\xd9\\x00u\\x00Q\\xa3\\xb0\\xf5\\xfd\\x01y\\x9cVm\\xb87x\\x8f\\x0c\\xa4z\\xcc\\x1b\\'\\xcb\\xf7\\x9e\\x88B\\x9a\\r\\xfe\\xd4\\x8b\\x05\\xe5\\x00\\x00\\x01r\\xefR\\x0f+\\x00\\x00\\x04\\x03\\x00F0D\\x02 ?\\xf1\\xe9a5\\xf5\\xb8%\\xaf\\xf6\\xa5\\x01\\x1e][\\'N\\xee^am>\\x83\\xfc\\xa1k\\xc5\\xd5A >2\\x02 z\\x00\\xf4w\\x18<d\\x13{\\xcd[\\xcb\\xa3k\\x1a\\x97\\xb7[\\xb8\\'^\\r\\xf3\\xccw!\\xe6\\xd1\\xa5@\\xd9\\x95",
                        "name": "ct_precert_scts",
                    },
                ],
                "fingerprint": {
                    "sha256": "8548c7021a2310d82e2d37bbbae374c67587fa4da81d1ea33d8c2dd551246c2a",
                    "sha1": "34db068362ca0c5356cde44727c7bb2552a3fd4f",
                },
                "serial": 2899357035992737906989516748620396151,
                "issuer": {
                    "C": "US",
                    "OU": "www.digicert.com",
                    "O": "DigiCert Inc",
                    "CN": "GeoTrust RSA CA 2018",
                },
                "expired": False,
                "subject": {"CN": "*.swat.outpost24.com"},
            }
        },
        "expired": False,
        "subject": {"CN": "*.swat.outpost24.com"},
        "cipher": {
            "version": "TLSv1/SSLv3",
            "bits": 256,
            "name": "ECDHE-RSA-AES256-GCM-SHA384",
        },
        "trust": {
            "revoked": False,
            "browser": {"mozilla": True, "apple": True, "microsoft": True},
        },
    }
    # flake8: qa

    expected = copy.deepcopy(result)
    expected["ssl"]["cert"]["serial"] = str(expected["ssl"]["cert"]["serial"])

    assert sanitize_node(result) == expected


@pytest.fixture
def shodan_response():
    with open(os.path.join(os.path.dirname(__file__), "shodan_response.json")) as f:
        return json.load(f)


@pytest.fixture
def mock_shodan_get_host_api_response():
    with open(os.path.join(os.path.dirname(__file__), "shodan_get_host_response.json")) as f:
        return json.load(f)


@pytest.fixture
def mock_shodan_api(shodan_response):
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.shodan.io/shodan/host/search?query=Server:%20Burp%20Collaborator",
            json=shodan_response,
        )
        yield mock


@pytest.fixture
def mock_shodan_get_host_api(mock_shodan_get_host_api_response):
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.shodan.io/shodan/host/8.8.8.8?&key=foo",
            json=mock_shodan_get_host_api_response,
        )
        yield mock


def test_query_shodan(mock_shodan_api):
    shodan = GetShodanHostSearch()
    shodan.module.configuration = {
        "key": "1",
        "base_url": "https://api.shodan.io",
        "api_key": "foo",
    }
    results: dict = shodan.run({"query": "Server:%20Burp%20Collaborator"})
    assert isinstance(orjson.dumps(results), bytes)
    assert len(results["matches"]) == 100
    assert results["matches"][0]["hostnames"] == ["c2ce4d12.fsp.oleane.fr"]
    assert results["matches"][0]["_shodan"]["crawler"] == "cdd92e2d835a37d2798fa6c7105171f4d214012f"
    assert results["matches"][99]["hostnames"] == ["ec2-108-129-62-94.eu-west-1.compute.amazonaws.com"]


def test_get_shodan_host(mock_shodan_get_host_api):
    query_ip = "8.8.8.8"
    shodan = GetShodanHost()
    shodan.module.configuration = {
        "api_key": "foo",
        "base_url": "https://api.shodan.io",
    }
    results: dict = shodan.run({"ip": query_ip})
    assert results != []
    assert isinstance(orjson.dumps(results), bytes)
    assert results["ip_str"] == query_ip


@pytest.mark.skipif("{'SHODAN_APIKEY'}.issubset(os.environ.keys()) == False")
def test_get_shodan_host_search_with_credentials():
    shodan = GetShodanHostSearch()
    shodan.module.configuration = {
        "api_key": os.environ["SHODAN_APIKEY"],
        "base_url": "https://api.shodan.io",
    }
    results: dict = shodan.run({"query": "8.8.8.8"})
    assert results != []
    assert isinstance(orjson.dumps(results), bytes)
    assert len(results["matches"]) == 100


@pytest.mark.skipif("{'SHODAN_APIKEY'}.issubset(os.environ.keys()) == False")
def test_get_shodan_host_with_credentials():
    query_ip = "8.8.8.8"
    shodan = GetShodanHost()
    shodan.module.configuration = {
        "api_key": os.environ["SHODAN_APIKEY"],
        "base_url": "https://api.shodan.io",
    }
    results: dict = shodan.run({"ip": query_ip})
    assert results != []
    assert isinstance(orjson.dumps(results), bytes)
    assert results["ip_str"] == query_ip
