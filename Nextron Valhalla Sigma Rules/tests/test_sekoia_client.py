import pytest
import requests_mock

from nextron_valhalla_sigma_rules_modules import sekoia_client
from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    LIST_PAGE_SIZE,
    MAX_LIST_PAGES,
    SekoiaAPIError,
    SekoiaClient,
    SekoiaRuleNotFoundError,
)

BASE_URL = "https://api.sekoia.io"
RULES_URL = f"{BASE_URL}/v1/sic/conf/rules-catalog/rules"


def test_create_rule_posts_with_bearer_and_returns_uuid():
    client = SekoiaClient(BASE_URL, "secret-token")

    with requests_mock.Mocker() as m:
        m.post(
            RULES_URL,
            json={"uuid": "rule-uuid-1"},
        )
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
        m.post(
            RULES_URL,
            json={"uuid": "u"},
        )
        client.create_rule({})
        assert m.last_request.url == RULES_URL


def test_update_rule_puts_with_uuid_in_path():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/the-uuid",
            status_code=200,
        )
        body = {"name": "X"}
        client.update_rule("the-uuid", body)

        assert m.last_request.method == "PUT"
        assert m.last_request.json() == body
        assert m.last_request.headers["Authorization"] == "Bearer k"


def test_create_rule_raises_on_http_error():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.post(
            RULES_URL,
            status_code=403,
        )
        with pytest.raises(Exception):
            client.create_rule({})


def test_update_rule_raises_rule_not_found_on_404():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/u",
            status_code=404,
        )
        with pytest.raises(SekoiaRuleNotFoundError) as excinfo:
            client.update_rule("u", {})
        assert excinfo.value.status_code == 404


def test_update_rule_403_au202_is_not_treated_as_not_found():
    """403 is documented as "Insufficient permissions". Even with code AU202
    it must surface as a generic error, never as "rule gone" (which would
    make the sync re-create the rule on every run)."""
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/u",
            status_code=403,
            text='{"message":"Insufficient permissions","code":"AU202"}',
        )
        with pytest.raises(SekoiaAPIError) as excinfo:
            client.update_rule("u", {})
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)
        assert excinfo.value.status_code == 403


def test_update_rule_raises_generic_error_on_400():
    client = SekoiaClient(BASE_URL, "k")

    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/u",
            status_code=400,
        )
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


# ---------------------------------------------------------------------------
# iter_rules — pagination + author filter
# ---------------------------------------------------------------------------

END_OF_LIST = {"json": {"items": []}}


def _offsets(mocker) -> list[str]:
    """The ``offset`` query param of each request made, in order."""
    return [req.qs["offset"][0] for req in mocker.request_history]


def test_iter_rules_yields_all_items_across_pages():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        # Page 1: full page.
        m.get(
            RULES_URL,
            [
                {"json": {"items": [{"uuid": f"sk-{i}"} for i in range(100)]}},
                {"json": {"items": [{"uuid": "sk-100"}, {"uuid": "sk-101"}]}},
                END_OF_LIST,
            ],
        )
        uuids = [r["uuid"] for r in client.iter_rules()]
        assert uuids == [f"sk-{i}" for i in range(102)]


def test_iter_rules_stops_on_an_empty_page_not_a_short_one():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            [
                {"json": {"items": [{"uuid": "sk-1"}, {"uuid": "sk-2"}]}},
                {"json": {"items": [{"uuid": "sk-3"}]}},
                END_OF_LIST,
            ],
        )
        uuids = [r["uuid"] for r in client.iter_rules()]
        assert uuids == ["sk-1", "sk-2", "sk-3"]
        assert m.call_count == 3


def test_iter_rules_walks_every_page_when_server_caps_the_page_size():
    server_cap = 10
    all_rules = [{"uuid": f"sk-{i}"} for i in range(25)]
    pages = [{"json": {"items": all_rules[i : i + server_cap]}} for i in range(0, len(all_rules), server_cap)]

    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, [*pages, END_OF_LIST])
        uuids = [r["uuid"] for r in client.iter_rules()]

        assert uuids == [f"sk-{i}" for i in range(25)]
        assert _offsets(m) == ["0", "10", "20", "25"]
        assert m.request_history[0].qs["limit"] == ["100"]


def test_iter_rules_returns_nothing_on_an_empty_first_page():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, json={"items": []})
        assert list(client.iter_rules()) == []
        assert m.call_count == 1


def test_iter_rules_raises_rather_than_looping_when_offset_is_ignored(monkeypatch):
    monkeypatch.setattr(sekoia_client, "MAX_LIST_PAGES", 5)
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, json={"items": [{"uuid": "sk-1"}]})
        with pytest.raises(SekoiaAPIError, match="did not terminate"):
            list(client.iter_rules())
        assert m.call_count == 5


def test_max_list_pages_is_generous_enough_for_a_real_tenant():
    assert MAX_LIST_PAGES * LIST_PAGE_SIZE >= 1_000_000


def test_iter_rules_falls_back_to_data_key_when_no_items_key():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            [
                {"json": {"data": [{"uuid": "sk-1"}, {"uuid": "sk-2"}]}},
                {"json": {"data": []}},
            ],
        )
        uuids = [r["uuid"] for r in client.iter_rules()]
        assert uuids == ["sk-1", "sk-2"]


def test_iter_rules_raises_on_http_error():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            status_code=500,
        )
        with pytest.raises(Exception):
            list(client.iter_rules())


def test_iter_rules_raises_on_non_json_body():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            text="not json",
        )
        with pytest.raises(Exception):
            list(client.iter_rules())


# ---------------------------------------------------------------------------
# get_rule — new for the "preserve user ``enabled`` on PUT" fix
# ---------------------------------------------------------------------------


def test_get_rule_returns_json():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            f"{RULES_URL}/sk-1",
            json={"uuid": "sk-1", "enabled": True, "name": "n"},
        )
        rule = client.get_rule("sk-1")
        assert rule == {"uuid": "sk-1", "enabled": True, "name": "n"}
        assert m.last_request.method == "GET"
        assert m.last_request.headers["Authorization"] == "Bearer k"


def test_get_rule_raises_not_found_on_404():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(f"{RULES_URL}/gone", status_code=404)
        with pytest.raises(SekoiaRuleNotFoundError) as excinfo:
            client.get_rule("gone")
        assert excinfo.value.status_code == 404


def test_get_rule_403_au202_is_not_treated_as_not_found():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            f"{RULES_URL}/u",
            status_code=403,
            text='{"message":"Insufficient permissions","code":"AU202"}',
        )
        with pytest.raises(SekoiaAPIError) as excinfo:
            client.get_rule("u")
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_get_rule_raises_generic_on_403_without_au202():
    """Plain permission problem — the trigger must NOT misread this as
    ``stale uuid, re-POST`` or every workspace-scope mistake would
    silently duplicate the entire catalog."""
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            f"{RULES_URL}/u",
            status_code=403,
            text='{"message":"Insufficient permissions","code":"AU101"}',
        )
        with pytest.raises(Exception) as excinfo:
            client.get_rule("u")
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_get_rule_raises_generic_on_403_with_non_json_body():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(f"{RULES_URL}/u", status_code=403, text="forbidden (plain text)")
        with pytest.raises(Exception) as excinfo:
            client.get_rule("u")
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_get_rule_raises_on_non_json_200_body():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(f"{RULES_URL}/u", text="not json")
        with pytest.raises(SekoiaAPIError):
            client.get_rule("u")


# ---------------------------------------------------------------------------
# PUT behaviour — new "403-must-be-AU202" assertion
# ---------------------------------------------------------------------------


def test_update_rule_raises_generic_on_403_without_au202():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.put(
            f"{RULES_URL}/u",
            status_code=403,
            text='{"message":"Insufficient permissions","code":"AU101"}',
        )
        with pytest.raises(Exception) as excinfo:
            client.update_rule("u", {})
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_update_rule_raises_generic_on_403_with_non_json_body():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/u", status_code=403, text="forbidden (plain text)")
        with pytest.raises(Exception) as excinfo:
            client.update_rule("u", {})
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


# ---------------------------------------------------------------------------
# Retry adapter — POST must not be retried (duplicates on read-timeout)
# ---------------------------------------------------------------------------


def test_retry_adapter_excludes_post():
    """A read-timeout on POST would otherwise cause urllib3 to re-POST,
    creating a duplicate rule whose uuid we never see. Keep GET and PUT
    (idempotent on this API) in the retry set; drop POST."""
    client = SekoiaClient(BASE_URL, "k")
    adapter = client._session.get_adapter("https://x")
    assert adapter.max_retries.allowed_methods == frozenset({"GET", "PUT"})


# ---------------------------------------------------------------------------
# Second review round: https guard, create_rule uuid, tag/community filters,
# total-based stop, disable endpoint, alert types, ATT&CK lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["http://api.sekoia.io", "api.sekoia.io", "ftp://x"])
def test_constructor_rejects_non_https_base_url(url):
    with pytest.raises(ValueError, match="https://"):
        SekoiaClient(url, "k")


def test_constructor_accepts_uppercase_https_scheme():
    SekoiaClient("HTTPS://api.sekoia.io", "k")


def test_create_rule_requires_uuid_field():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.post(RULES_URL, json={"id": "legacy-id"})
        with pytest.raises(SekoiaAPIError, match="no uuid"):
            client.create_rule({})


def test_iter_rules_stops_when_offset_reaches_total():
    """With ``total`` in the body no extra empty-page request is needed."""
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            [
                {"json": {"items": [{"uuid": "a"}, {"uuid": "b"}], "total": 3}},
                {"json": {"items": [{"uuid": "c"}], "total": 3}},
            ],
        )
        assert [r["uuid"] for r in client.iter_rules(page_size=2)] == ["a", "b", "c"]
        assert m.call_count == 2
        assert _offsets(m) == ["0", "2"]


def test_iter_rules_sends_tag_and_community_filters():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, json={"items": [], "total": 0})
        list(client.iter_rules(tag_name="nextron-valhalla", community_uuid="c-1"))
        qs = m.last_request.qs
        assert qs["match[tag_name]"] == ["nextron-valhalla"]
        assert qs["match[community_uuid]"] == ["c-1"]


def test_iter_rules_client_side_tag_and_community_filter():
    """If the server ignores the filters, nothing outside them is yielded."""
    client = SekoiaClient(BASE_URL, "k")
    items = [
        {"uuid": "ok", "community_uuid": "c-1", "tags": [{"uuid": "t", "name": "nextron-valhalla"}]},
        {"uuid": "ok-str-tag", "community_uuid": "c-1", "tags": ["nextron-valhalla"]},
        {"uuid": "no-tag", "community_uuid": "c-1", "tags": [{"uuid": "t", "name": "other"}]},
        {"uuid": "other-community", "community_uuid": "c-2", "tags": ["nextron-valhalla"]},
    ]
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, json={"items": items, "total": len(items)})
        uuids = [r["uuid"] for r in client.iter_rules(tag_name="nextron-valhalla", community_uuid="c-1")]
        assert uuids == ["ok", "ok-str-tag"]


def test_iter_rules_error_mid_scan_raises():
    """A failure on page 2 must raise, never yield a silently partial list."""
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            RULES_URL,
            [
                {"json": {"items": [{"uuid": "a"}], "total": 5}},
                {"status_code": 502, "text": "bad gateway"},
            ],
        )
        with pytest.raises(SekoiaAPIError, match="502"):
            list(client.iter_rules(page_size=1))


def test_iter_rules_rejects_non_dict_body():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(RULES_URL, json=[{"uuid": "a"}])
        with pytest.raises(SekoiaAPIError, match="unexpected list shape"):
            list(client.iter_rules())


def test_disable_rule_uses_dedicated_endpoint():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/sk-1/disabled", status_code=200, json={})
        client.disable_rule("sk-1")
        assert m.last_request.method == "PUT"
        assert m.last_request.body is None


def test_disable_rule_raises_not_found_on_404():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/gone/disabled", status_code=404)
        with pytest.raises(SekoiaRuleNotFoundError):
            client.disable_rule("gone")


def test_disable_rule_raises_on_403():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.put(f"{RULES_URL}/u/disabled", status_code=403, text="{}")
        with pytest.raises(SekoiaAPIError) as excinfo:
            client.disable_rule("u")
        assert not isinstance(excinfo.value, SekoiaRuleNotFoundError)


def test_list_alert_types_paginates():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE_URL}/v1/sic/conf/alerts/types",
            [
                {"json": {"items": [{"uuid": "t1"}], "total": 2}},
                {"json": {"items": [{"uuid": "t2"}], "total": 2}},
            ],
        )
        assert [t["uuid"] for t in client.list_alert_types(page_size=1)] == ["t1", "t2"]


def test_find_attack_pattern_returns_stix_id():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE_URL}/v2/inthreat/objects",
            json={"items": [{"id": "x-mitre-tactic--1"}, {"id": "attack-pattern--abc"}]},
        )
        assert client.find_attack_pattern("T1059") == "attack-pattern--abc"
        assert m.last_request.qs["match[external_id]"] == ["t1059"]


def test_find_attack_pattern_returns_none_when_unknown():
    client = SekoiaClient(BASE_URL, "k")
    with requests_mock.Mocker() as m:
        m.get(f"{BASE_URL}/v2/inthreat/objects", json={"items": []})
        assert client.find_attack_pattern("T9999") is None
