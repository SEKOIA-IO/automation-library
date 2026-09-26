import pytest
import requests_mock

from nextron_valhalla_sigma_rules_modules.client import (
    VALHALLA_BASE_URL,
    ValhallaClient,
)


def test_get_sigma_feed_posts_form_encoded_apikey():
    client = ValhallaClient("deadbeef")

    with requests_mock.Mocker() as m:
        m.post(
            f"{VALHALLA_BASE_URL}/api/v1/getsigma",
            json={"rules": [{"filename": "a.yml", "content": "title: a"}]},
        )
        rules = client.get_sigma_feed()

        assert len(m.request_history) == 1
        req = m.request_history[0]
        assert req.headers["Content-Type"].startswith(
            "application/x-www-form-urlencoded"
        )
        assert "apikey=deadbeef" in req.text
        assert "format=json" in req.text

    assert rules == [{"filename": "a.yml", "content": "title: a"}]


def test_get_sigma_feed_targets_hardcoded_valhalla_url():
    client = ValhallaClient("k")

    with requests_mock.Mocker() as m:
        m.post(f"{VALHALLA_BASE_URL}/api/v1/getsigma", json={"rules": []})
        client.get_sigma_feed()
        assert m.last_request.url == f"{VALHALLA_BASE_URL}/api/v1/getsigma"


def test_get_sigma_feed_raises_on_status_error_payload():
    client = ValhallaClient("bad")

    with requests_mock.Mocker() as m:
        m.post(
            f"{VALHALLA_BASE_URL}/api/v1/getsigma",
            json={"status": "error", "message": "invalid api key"},
        )
        with pytest.raises(RuntimeError, match="invalid api key"):
            client.get_sigma_feed()


def test_get_sigma_feed_raises_for_http_error():
    client = ValhallaClient("k")

    with requests_mock.Mocker() as m:
        m.post(f"{VALHALLA_BASE_URL}/api/v1/getsigma", status_code=500)
        with pytest.raises(Exception):
            client.get_sigma_feed()


def test_get_sigma_feed_returns_empty_when_no_rules_key():
    client = ValhallaClient("k")

    with requests_mock.Mocker() as m:
        m.post(f"{VALHALLA_BASE_URL}/api/v1/getsigma", json={})
        assert client.get_sigma_feed() == []
