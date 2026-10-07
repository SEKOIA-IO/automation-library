from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest
from sekoia_automation.storage import PersistentJSON

from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector

PREVIOUS_CHECKPOINT = "20200101000000.0Z"


def user_entry(name: str, sid: str, created_at: datetime) -> dict[str, Any]:
    return {
        "dn": f"CN={name},DC=example,DC=com",
        "attributes": {"userPrincipalName": f"{name}@example.com", "objectSid": sid, "whenCreated": created_at},
    }


def response(status_code: int) -> Mock:
    res = Mock(status_code=status_code)
    res.json.return_value = {}
    return res


@pytest.fixture
def connector(tmp_path):
    connector = object.__new__(MicrosoftADUserAssetConnector)
    connector.module = Mock()
    connector._configuration = Mock(batch_size=1, frequency=0, sekoia_base_url="https://api.example.com")
    connector._data_path = tmp_path
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.ldap_client = Mock()
    connector.context = PersistentJSON("context.json", tmp_path)
    connector._latest_time = None
    connector._seen_sids = set()
    connector._cycle_latest_time = None
    connector._cycle_seen_sids = set()
    connector._push_failed = False
    # Only the HTTP layer is faked: the SDK push code, which commits the checkpoint after each push, runs for real.
    connector._http_session = Mock()

    with connector.context as cache:
        cache["most_recent_datetime"] = PREVIOUS_CHECKPOINT
        cache["seen_sids_at_checkpoint"] = ["S-OLD"]

    return connector


def test_complete_cycle_commits_newest_date(connector):
    # Paged LDAP results are not ordered by creation date
    connector.ldap_client.extend.standard.paged_search.return_value = iter(
        [
            user_entry("newest", "S-NEW", datetime(2024, 6, 1)),
            user_entry("older", "S-OLD-2", datetime(2023, 1, 1)),
        ]
    )
    connector._http_session.post.return_value = response(200)

    connector.asset_fetch_cycle()

    assert connector._http_session.post.call_count == 2
    assert connector.most_recent_datetime == "20240601000000.0Z"
    assert connector.seen_sids_at_checkpoint == {"S-NEW"}


def test_interrupted_cycle_keeps_previous_checkpoint(connector):
    def interrupted_search(**_: Any) -> Iterator[dict[str, Any]]:
        yield user_entry("newest", "S-NEW", datetime(2024, 6, 1))
        yield user_entry("older", "S-OLD-2", datetime(2023, 1, 1))
        raise RuntimeError("runner stopped")

    connector.ldap_client.extend.standard.paged_search.side_effect = interrupted_search
    connector._http_session.post.return_value = response(200)

    with pytest.raises(RuntimeError):
        connector.asset_fetch_cycle()

    # Two users were pushed, but users not read yet may be older: the next cycle must collect them.
    assert connector._http_session.post.call_count == 2
    assert connector.most_recent_datetime == PREVIOUS_CHECKPOINT
    assert connector.seen_sids_at_checkpoint == {"S-OLD"}


def test_failed_push_keeps_previous_checkpoint(connector):
    connector.ldap_client.extend.standard.paged_search.return_value = iter(
        [
            user_entry("lost", "S-LOST", datetime(2023, 1, 1)),
            user_entry("newest", "S-NEW", datetime(2024, 6, 1)),
        ]
    )
    connector._http_session.post.side_effect = [response(500), response(200)]

    connector.asset_fetch_cycle()

    assert connector.most_recent_datetime == PREVIOUS_CHECKPOINT
    assert connector.seen_sids_at_checkpoint == {"S-OLD"}


def test_failed_push_is_forgotten_on_next_cycle(connector):
    connector.ldap_client.extend.standard.paged_search.side_effect = [
        iter([user_entry("newest", "S-NEW", datetime(2024, 6, 1))]),
        iter([user_entry("newest", "S-NEW", datetime(2024, 6, 1))]),
    ]
    connector._http_session.post.side_effect = [response(500), response(200)]

    connector.asset_fetch_cycle()
    connector.asset_fetch_cycle()

    assert connector.most_recent_datetime == "20240601000000.0Z"


def test_empty_cycle_keeps_previous_checkpoint(connector):
    connector.ldap_client.extend.standard.paged_search.return_value = iter([])

    connector.asset_fetch_cycle()

    connector._http_session.post.assert_not_called()
    assert connector.most_recent_datetime == PREVIOUS_CHECKPOINT
