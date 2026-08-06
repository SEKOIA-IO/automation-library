import hashlib

import pytest
import requests_mock

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.blocklist.action_create_blocklist_item import (
    CreateBlocklistItemAction,
    CreateBlocklistItemActionArguments,
)
from sentinelone_module.blocklist.action_delete_blocklist_item import (
    DeleteBlocklistItemAction,
    DeleteBlocklistItemActionArguments,
)


def _sha1(st: str) -> str:
    encoded_string = st.encode("utf-8")
    sha1_hash = hashlib.sha1(encoded_string)
    return sha1_hash.hexdigest()


@pytest.fixture
def create_blocklist_response() -> dict:
    return {
        "data": [
            {
                "createdAt": "2026-03-20T08:18:31.986814Z",
                "description": None,
                "hashId": "1111111111111111111",
                "id": "2222222222222222222",
                "notRecommended": "NONE",
                "osType": "macos",
                "scope": {"groupIds": ["3333333333333333333"]},
                "scopeName": "group",
                "sha256Value": None,
                "source": "user",
                "type": "black_hash",
                "updatedAt": "2026-03-20T08:18:31.985838Z",
                "userId": "4444444444444444444",
                "userName": "Sekoia.io integration 2025",
                "value": _sha1("test"),
            }
        ]
    }


@pytest.fixture
def delete_blocklist_response() -> dict:
    return {"data": {"affected": 1}}


def test_create_blocklist(symphony_storage, create_blocklist_response):
    sentinelone_hostname = "example.sentinelone.net"
    module = SentinelOneModule()
    module.configuration = {
        "hostname": sentinelone_hostname,
        "api_token": "fake_sentinelone_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )

        mock.post(f"https://example.sentinelone.net/web/api/v2.1/restrictions", json=create_blocklist_response)

        args = CreateBlocklistItemActionArguments(
            os_type="linux", sha_1=_sha1("test"), filter_group_ids=["3333333333333333333"]
        )
        action = CreateBlocklistItemAction(module, symphony_storage)
        action.run(args)


@pytest.mark.parametrize(
    "args",
    [
        CreateBlocklistItemActionArguments(os_type="linux", sha_1=_sha1("test")),
        CreateBlocklistItemActionArguments(
            os_type="linux", sha_1=_sha1("test"), filter_tenant_scope=True, filter_group_ids=["3333333333333333333"]
        ),
        CreateBlocklistItemActionArguments(
            os_type="linux", sha_1=_sha1("test"), filter_tenant_scope=True, filter_account_ids=["1111111111111111111"]
        ),
        CreateBlocklistItemActionArguments(
            os_type="linux", sha_1=_sha1("test"), filter_tenant_scope=True, filter_site_ids=["3333333333333333333"]
        ),
        CreateBlocklistItemActionArguments(
            os_type="linux",
            sha_1=_sha1("test"),
            filter_account_ids=["1111111111111111111"],
            filter_group_ids=["3333333333333333333"],
        ),
        CreateBlocklistItemActionArguments(
            os_type="linux",
            sha_1=_sha1("test"),
            filter_site_ids=["1111111111111111111"],
            filter_group_ids=["3333333333333333333"],
        ),
        CreateBlocklistItemActionArguments(
            os_type="linux",
            sha_1=_sha1("test"),
            filter_account_ids=["1111111111111111111"],
            filter_site_ids=["3333333333333333333"],
        ),
    ],
)
def test_create_blocklist_filters(symphony_storage, create_blocklist_response, args):
    sentinelone_hostname = "example.sentinelone.net"
    module = SentinelOneModule()
    module.configuration = {
        "hostname": sentinelone_hostname,
        "api_token": "fake_sentinelone_api_key",
    }

    action = CreateBlocklistItemAction(module, symphony_storage)
    with pytest.raises(ValueError):
        action.run(args)


def test_delete_blocklist(symphony_storage, delete_blocklist_response):
    sentinelone_hostname = "example.sentinelone.net"
    module = SentinelOneModule()
    module.configuration = {
        "hostname": sentinelone_hostname,
        "api_token": "fake_sentinelone_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )

        mock.delete(f"https://example.sentinelone.net/web/api/v2.1/restrictions", json=delete_blocklist_response)

        args = DeleteBlocklistItemActionArguments(ids=["3333333333333333333"])
        action = DeleteBlocklistItemAction(module, symphony_storage)
        action.run(args)
