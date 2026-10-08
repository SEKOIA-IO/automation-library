import pytest
import requests_mock

from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaClient,
    SekoiaRuleNotFoundError,
)

BASE_URL = "https://api.sekoia.io"
RULES_URL = f"{BASE_URL}/v1/sic/conf/rules-catalog/rules"


def test_create_rule_posts_with_bearer_and_returns_uuid():
    client = SekoiaClient(BASE_URL, "secret-token")

    with requests_mock.Mocker() as m:
        m.post(RULES_URL, json={"uuid": "rule-uuid-1"},)
        body = {"name": "X", "type": "sigma"}
        uuid = client.create_rule(body)

        assert uuid == "rule-uuid-1"
        req = m.last_request
        assert req.headers["Authorization"] == "Bearer secret-token"
        assert req.headers["Content-Type"] == "application/json"
        assert req.json() == body


def test_create_rule_strips_trailing_slash_from_base_url():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.post(RULES_URL, json={"uuid": "u"},)
        client.create_rule({})
        assert (m.last_request.url == RULES_URL)


def test_update_rule_puts_with_uuid_in_path():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/the-uuid", status_code=200,)
        body = {"name": "X"}
        client.update_rule("the-uuid", body)

        assert m.last_request.method == "PUT"
        assert m.last_request.json() == body
        assert m.last_request.headers["Authorization"] == "Bearer k"


def test_create_rule_raises_on_http_error():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.post(RULES_URL, status_code=403,)
        with pytest.raises(Exception):
            client.create_rule({})


def test_update_rule_raises_rule_not_found_on_404():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/u", status_code=404,)
        with pytest.raises(SekoiaRuleNotFoundError) as excinfo:
            client.update_rule("u", {})
        assert excinfo.value.status_code == 404


def test_update_rule_raises_rule_not_found_on_403_au202():
    """Sekoia returns 403 (AU202) for PUT to a rule UUID that this API key
    doesn't own anymore (e.g. deleted rule). We treat it the same as 404."""
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/u",
            status_code=403,
            text='{"message":"Insufficient permissions","code":"AU202"}',
        )
        with pytest.raises(SekoiaRuleNotFoundError) as excinfo:
            client.update_rule("u", {})
        assert excinfo.value.status_code == 403


def test_update_rule_raises_generic_error_on_400():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/u", status_code=400,)
        with pytest.raises(Exception) as excinfo:
            client.update_rule("u", {})
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_supports_path_mounted_regional_base_url():
    client = SekoiaClient("https://app.fra2.sekoia.io/api", "k")

    with requests_mock.Mocker() as m:
        m.post(
            "https://app.fra2.sekoia.io/api/v1/sic/conf/rules-catalog/rules",
            json={"uuid": "x"},
        )
        client.create_rule({})
