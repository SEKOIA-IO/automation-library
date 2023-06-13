import json
import os

import pytest

from censys_module.view import ViewAction


@pytest.fixture
def ip_result():
    return {
        "tags": ["http"],
        "ip": "82.244.181.36",
        "updated_at": "2019-10-30T03:56:07+00:00",
        "autonomous_system": {
            "description": "PROXAD",
            "rir": "unknown",
            "routed_prefix": "82.224.0.0/11",
            "country_code": "FR",
            "path": [7018, 174, 12322, 12322, 12322, 12322],
            "asn": 12322,
            "name": "PROXAD",
        },
        "location": {
            "province": "Île-de-France",
            "city": "Versailles",
            "country": "France",
            "longitude": 2.1342,
            "registered_country": "France",
            "registered_country_code": "FR",
            "postal_code": "78000",
            "country_code": "FR",
            "latitude": 48.8036,
            "timezone": "Europe/Paris",
            "continent": "Europe",
        },
        "80": {
            "http": {
                "get": {
                    "body": '<!DOCTYPE HTML>\n<html>\n<head>\n    <meta charset="UTF-8">\n',
                    "title": "Freebox OS :: Identification",
                    "status_code": 200,
                    "status_line": "200 OK",
                    "headers": {
                        "unknown": [{"key": "date", "value": "Tue, 29 Oct 2019 14:48:21 GMT"}],
                        "expires": "Tue, 29 Oct 2019 14:48:20 GMT",
                        "server": "nginx",
                        "connection": "keep-alive",
                        "content_type": "text/html; charset=utf-8",
                        "cache_control": "no-cache",
                    },
                    "body_sha256": "978101ee3022579861027871ef01d351441bd981bbb8f8890deef5fac9a38d49",
                    "metadata": {"product": "nginx", "description": "nginx"},
                }
            }
        },
        "ports": [80],
        "protocols": ["80/http"],
    }


@pytest.fixture
def website_result():
    return {
        "domain": "lemonde.fr",
        "alexa_rank": 1622,
        "tags": ["smtp", "http", "https"],
        "updated_at": "2019-10-30T12:19:32+00:00",
        "0": {
            "lookup": {
                "dmarc": {"raw": "v=DMARC1; p=quarantine; sp=none; adkim=r; aspf=r; pct=100; "},
                "axfr": {
                    "support": False,
                    "truncated": False,
                    "servers": [
                        {
                            "status": "ERROR",
                            "error": "dns: bad xfr rcode: 5",
                            "server": "216.239.38.107",
                        },
                        {
                            "status": "ERROR",
                            "error": "dns: bad xfr rcode: 5",
                            "server": "216.239.32.107",
                        },
                        {
                            "status": "ERROR",
                            "error": "dns: bad xfr rcode: 5",
                            "server": "216.239.36.107",
                        },
                        {
                            "status": "ERROR",
                            "error": "dns: bad xfr rcode: 5",
                            "server": "216.239.34.107",
                        },
                    ],
                },
                "spf": {"raw": "v=spf1 include:spf1.lemonde.fr include:spf2.lemonde.fr"},
            }
        },
        "ports": [80, 25, 443],
        "protocols": [
            "443/https_www",
            "80/http",
            "80/http_www",
            "443/https",
            "25/smtp",
        ],
    }


@pytest.fixture
def certificate_result():
    return {
        "parent_spki_subject_fingerprint": "340ffdeae9152c43ef716c6e790f869029dbb48a0f36a5b0756dd74e2b1e242d",
        "tags": ["unexpired", "leaf", "google-ct", "dv", "precert", "trusted", "ct"],
        "ct": {
            "google_pilot": {
                "index": 765_706_315,
                "ct_to_censys_at": "2019-09-24T15:59:58+00:00",
                "added_to_ct_at": "2019-09-24T15:58:55+00:00",
            },
            "cloudflare_nimbus_2020": {
                "index": 65_582_987,
                "ct_to_censys_at": "2019-09-24T17:13:46+00:00",
                "added_to_ct_at": "2019-09-24T15:58:56+00:00",
            },
        },
        "raw": "MIIFUTCCBDmgAwIBAgIIIoQiJ69zx7YwDQYJKoZIhvcNAQELBQAwgbQxCzAJBgNVBAYTAlVTMRAwDgYDVQQIEwdBcml6",
        "parents": [],
        "zlint": {
            "version": 3,
            "errors_present": False,
            "fatals_present": False,
            "warnings_present": False,
            "lints": {"n_subject_common_name_included": False},
            "notices_present": False,
        },
        "precert": False,
        "metadata": {
            "post_processed": False,
            "parse_status": "success",
            "updated_at": "2019-09-24T17:20:15",
            "added_at": "2019-09-24T16:14:57+00:00",
            "source": "ct",
            "seen_in_scan": False,
            "parse_version": 0,
        },
    }


@pytest.fixture
def action():
    action = ViewAction()
    action.module.configuration = {"api_user_id": "foo", "api_user_secret": "bar"}
    yield action


def mock_request(censys_mock, arguments, json):
    censys_mock.get(
        f'https://www.censys.io/api/v1/view/{arguments["index"]}/{arguments["item"]}',
        json=json,
    )


def validate_result(res, expected, storage):
    assert "result_path" in res
    file_path = os.path.join(storage, res["result_path"])
    assert os.path.isfile(file_path)
    with open(file_path) as fp:
        loaded = json.load(fp)
    assert loaded == expected


def test_view_ip(action, symphony_storage, ip_result, censys_mock):
    arguments = {"index": "ipv4", "item": "8.8.8.8"}
    mock_request(censys_mock, arguments, ip_result)
    res = action.run(arguments)
    validate_result(res, ip_result, symphony_storage)


def test_view_website(action, symphony_storage, website_result, censys_mock):
    arguments = {"index": "websites", "item": "8.8.8.8"}
    mock_request(censys_mock, arguments, website_result)
    res = action.run(arguments)
    validate_result(res, website_result, symphony_storage)


def test_view_certificate(action, symphony_storage, certificate_result, censys_mock):
    arguments = {
        "index": "certificates",
        "item": "51741345298007d2268a15c5ba0b6ba1f604e6001f7ae228c206fadeebdf5997",
    }
    mock_request(censys_mock, arguments, certificate_result)
    res = action.run(arguments)
    validate_result(res, certificate_result, symphony_storage)
