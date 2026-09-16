import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests_mock

from microsoft_ad.actions_base import MicrosoftADModule
from microsoft_ad.sync_assets_actions import SynchronizeAssetsAction

ASSETS_URL = "https://api.sekoia.io/api/v2/asset-management/assets"
COMMUNITY = "community-1"


@pytest.fixture
def action():
    module = MicrosoftADModule()
    action = SynchronizeAssetsAction(module)
    action.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password",
    }
    return action


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr("time.sleep", calls.append)
    return calls


def arguments(**overrides):
    return {
        "basedn": "DC=example,DC=com",
        "asset_synchronization_configuration": {
            "asset_name_field": "sAMAccountName",
            "detection_properties": {"email": ["mail"]},
            "contextual_properties": {"department": "department", "created": "whenCreated"},
        },
        "community_uuid": COMMUNITY,
        "sekoia_api_key": "api-key",
        "delay_between_requests": 0,
        **overrides,
    }


def ldap_entry(**attributes):
    return {"type": "searchResEntry", "dn": f"CN={attributes.get('sAMAccountName')}", "attributes": attributes}


def run(action, entries, args=None):
    with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as client:
        client.extend.standard.paged_search.return_value = iter(entries)
        results = action.run(args or arguments())
    return results, client


def search_matcher(search, in_detection_properties=False):
    def match(request):
        qs = request.qs
        return (
            qs.get("search") == [search.lower()]
            and ("also_search_in_detection_properties" in qs) == in_detection_properties
        )

    return match


def test_create_asset_and_merge_found_ones(action, sleeps):
    created = datetime(2024, 1, 2, tzinfo=timezone.utc)
    entry = ldap_entry(sAMAccountName="jdoe", mail=["jdoe@example.com"], department="IT", whenCreated=created)

    with requests_mock.Mocker() as mock:
        mock.get(
            ASSETS_URL,
            additional_matcher=search_matcher("jdoe@example.com", True),
            json={"items": [{"uuid": "old-1", "name": "jdoe@example.com"}]},
        )
        mock.get(
            ASSETS_URL,
            additional_matcher=search_matcher("jdoe"),
            json={"items": [{"uuid": "other", "name": "jdoe2"}]},
        )
        mock.post(ASSETS_URL, json={"uuid": "new-1"})
        mock.post(f"{ASSETS_URL}/merge", json={})

        results, client = run(action, [entry, {"type": "searchResRef"}])

        assert results == {"total": 1, "created": 1, "updated": 0, "merged": 1, "skipped": 0}
        assert client.extend.standard.paged_search.call_args.kwargs["attributes"] == [
            "department",
            "mail",
            "sAMAccountName",
            "whenCreated",
        ]

        for request in [r for r in mock.request_history if r.method == "GET"]:
            assert request.qs["community_uuids"] == [COMMUNITY]
            assert request.headers["Authorization"] == "Bearer api-key"

        create = next(r for r in mock.request_history if r.method == "POST" and r.url == ASSETS_URL)
        assert create.json() == {
            "name": "jdoe",
            "description": "",
            "type": "account",
            "category": "user",
            "reviewed": True,
            "source": "manual",
            "props": {"department": "IT", "created": created.isoformat()},
            "atoms": {"email": ["jdoe@example.com"]},
            "community_uuid": COMMUNITY,
        }
        merge = next(r for r in mock.request_history if r.url.endswith("/merge"))
        assert merge.json() == {"destination": "new-1", "sources": ["old-1"]}


def test_update_existing_asset(action, sleeps):
    entry = ldap_entry(sAMAccountName="jdoe", mail=[], department=[], whenCreated=[])

    with requests_mock.Mocker() as mock:
        mock.get(ASSETS_URL, json={"items": [{"uuid": "asset-1", "name": "JDOE"}]})
        mock.put(f"{ASSETS_URL}/asset-1", json={})

        results, _ = run(action, [entry])

        assert results == {"total": 1, "created": 0, "updated": 1, "merged": 0, "skipped": 0}
        update = mock.request_history[-1]
        assert update.method == "PUT"
        assert update.json()["atoms"] == {}
        assert update.json()["props"] == {}
        assert "community_uuid" not in update.json()


def test_skip_users_without_name_or_with_ambiguous_match(action, sleeps):
    entries = [ldap_entry(sAMAccountName=[], mail=[]), ldap_entry(sAMAccountName="jdoe", mail=[])]

    with requests_mock.Mocker() as mock:
        mock.get(ASSETS_URL, json={"items": [{"uuid": "a", "name": "jdoe"}, {"uuid": "b", "name": "jdoe"}]})

        results, _ = run(action, entries)

    assert results == {"total": 2, "created": 0, "updated": 0, "merged": 0, "skipped": 2}


def test_retry_on_rate_limit_with_retry_after(action, sleeps):
    entry = ldap_entry(sAMAccountName="jdoe")
    args = arguments(
        delay_between_requests=0.5,
        asset_synchronization_configuration={"asset_name_field": "sAMAccountName"},
    )

    with requests_mock.Mocker() as mock:
        mock.get(
            ASSETS_URL,
            [
                {"status_code": 429, "headers": {"Retry-After": "7"}},
                {"status_code": 503},
                {"json": {"items": []}},
            ],
        )
        mock.post(ASSETS_URL, json={"uuid": "new-1"})

        results, _ = run(action, [entry], args)

    assert results["created"] == 1
    # throttle before each call, Retry-After honoured, exponential backoff without header
    assert sleeps == [0.5, 7.0, 0.5, 2.0, 0.5, 0.5]


def test_abort_when_retries_exhausted(action, sleeps):
    with requests_mock.Mocker() as mock:
        mock.get(ASSETS_URL, status_code=429, headers={"Retry-After": "not-a-number"})

        with pytest.raises(Exception, match="HTTP 429"):
            run(action, [ldap_entry(sAMAccountName="jdoe")])

        assert mock.call_count == 5


def test_abort_on_client_error(action, sleeps):
    with requests_mock.Mocker() as mock:
        mock.get(ASSETS_URL, json={"items": []})
        mock.post(ASSETS_URL, status_code=403, text="forbidden")

        with pytest.raises(Exception, match="HTTP 403 .* forbidden"):
            run(action, [ldap_entry(sAMAccountName="jdoe")])

        assert mock.call_count == 2
