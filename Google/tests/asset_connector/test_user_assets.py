from unittest.mock import MagicMock, Mock, patch

import httplib2
import pytest
from googleapiclient.errors import HttpError
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.module import Module

from google_module.asset_connector.user_assets import KNOWN_USERS_KEY, GoogleWorkspaceUserAssetConnector

ADMIN_USER = {
    "id": "100000000000000000001",
    "primaryEmail": "jane.doe@example.com",
    "name": {"givenName": "Jane", "familyName": "Doe", "fullName": "Jane Doe", "displayName": "Jane D."},
    "isAdmin": True,
    "isDelegatedAdmin": False,
    "suspended": False,
    "archived": False,
    "isEnrolledIn2Sv": True,
    "lastLoginTime": "2026-09-28T08:15:00.000Z",
    "creationTime": "2021-03-01T10:00:00.000Z",
    "orgUnitPath": "/Engineering",
    "organizations": [
        {"name": "Other Corp", "title": "Consultant"},
        {"name": "Example Corp", "title": "CTO", "department": "Engineering", "location": "Paris", "primary": True},
    ],
    "externalIds": [{"type": "custom", "value": "X-1"}, {"type": "organization", "value": "E-42"}],
    "etag": '"etag-1"',
}

SUSPENDED_USER = {
    "id": "100000000000000000002",
    "primaryEmail": "john.smith@example.com",
    "suspended": True,
    "isEnrolledIn2Sv": False,
    "lastLoginTime": "1970-01-01T00:00:00.000Z",
    "creationTime": "2024-01-10T08:00:00.000Z",
    "orgUnitPath": "/",
}

GROUP = {"id": "group-1", "email": "engineering@example.com", "name": "Engineering", "description": "Engineers"}


@pytest.fixture
def connector(tmp_path, credentials):
    module = Module()
    module.configuration = {"credentials": credentials}
    connector = GoogleWorkspaceUserAssetConnector(module=module, data_path=tmp_path)
    connector.configuration = {
        "sekoia_base_url": "https://api.sekoia.io",
        "sekoia_api_key": "api-key",
        "admin_mail": "admin@example.com",
        "frequency": 86400,
        "batch_size": 1,
    }
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.directory = MagicMock()
    return connector


def serve(connector, user_pages, groups=(), members=None):
    directory = connector.directory
    directory.users.return_value.list.return_value.execute.side_effect = list(user_pages)
    directory.groups.return_value.list.return_value.execute.return_value = {"groups": list(groups)}
    directory.members.return_value.list.side_effect = lambda groupKey, **_: Mock(
        execute=Mock(return_value={"members": (members or {}).get(groupKey, [])})
    )


def test_directory_impersonates_admin(connector, credentials):
    del connector.directory
    with (
        patch("google_module.asset_connector.user_assets.service_account.Credentials") as credentials_class,
        patch("google_module.asset_connector.user_assets.build") as build,
    ):
        assert connector.directory is build.return_value

    credentials_class.from_service_account_info.assert_called_once_with(credentials, scopes=connector.SCOPES)
    delegated = credentials_class.from_service_account_info.return_value.with_subject
    delegated.assert_called_once_with("admin@example.com")
    build.assert_called_once_with("admin", "directory_v1", credentials=delegated.return_value, cache_discovery=False)


def test_map_fields_admin_user(connector):
    asset = connector.map_fields(ADMIN_USER, [Group(uid="group-1", name="Engineering")])

    assert asset.class_uid == 5003
    assert asset.type_uid == 500302
    assert asset.time == 1614592800.0
    assert asset.metadata.product.name == "Google Workspace"
    user = asset.user
    assert user.uid == "100000000000000000001"
    assert user.name == user.email_addr == "jane.doe@example.com"
    assert user.full_name == "Jane Doe"
    assert user.display_name == "Jane D."
    assert user.domain == "example.com"
    assert user.has_mfa is True
    assert user.type == "Admin"
    assert user.account.type == "Google Workspace"
    assert [group.uid for group in user.groups] == ["group-1"]
    assert user.org.name == "Example Corp"
    assert user.org.ou_name == "/Engineering"
    assert user.ldap_person.model_dump() == {
        "given_name": "Jane",
        "surname": "Doe",
        "job_title": "CTO",
        "department": "Engineering",
        "office_location": "Paris",
        "employee_uid": "E-42",
    }
    assert asset.enrichments[0].data.is_enabled is True
    assert asset.enrichments[0].data.last_logon == "2026-09-28T08:15:00.000Z"


def test_map_fields_suspended_user_never_logged_in(connector):
    asset = connector.map_fields(SUSPENDED_USER, [])

    user = asset.user
    assert user.type == "User"
    assert user.has_mfa is False
    assert user.groups is None
    assert user.full_name is None
    assert user.org.name == "example.com"
    assert asset.enrichments[0].data.is_enabled is False
    assert asset.enrichments[0].data.last_logon is None


def test_map_fields_delegated_admin_and_archived(connector):
    asset = connector.map_fields(
        {**SUSPENDED_USER, "suspended": False, "archived": True, "isDelegatedAdmin": True}, []
    )

    assert asset.user.type == "Admin"
    assert asset.enrichments[0].data.is_enabled is False


def test_map_fields_null_fields(connector):
    asset = connector.map_fields({**SUSPENDED_USER, "name": None, "organizations": None, "externalIds": None}, [])

    assert asset.user.full_name is None
    assert asset.user.org.name == "example.com"
    assert asset.user.ldap_person.employee_uid is None


def test_get_assets_paginates_and_attaches_direct_groups(connector):
    serve(
        connector,
        [{"users": [ADMIN_USER], "nextPageToken": "page-2"}, {"users": [SUSPENDED_USER]}],
        groups=[GROUP],
        members={"group-1": [{"id": ADMIN_USER["id"], "type": "USER"}, {"id": "group-2", "type": "GROUP"}]},
    )

    assets = list(connector.get_assets())

    assert [asset.user.uid for asset in assets] == [ADMIN_USER["id"], SUSPENDED_USER["id"]]
    assert [group.name for group in assets[0].user.groups] == ["Engineering"]
    assert assets[1].user.groups is None
    users_list = connector.directory.users.return_value.list
    assert users_list.call_args_list[1].kwargs["pageToken"] == "page-2"
    assert users_list.call_args_list[1].kwargs["customer"] == "my_customer"
    users_list.return_value.execute.assert_called_with(num_retries=5)


def test_customer_member_group_applies_to_every_user(connector):
    everyone = {"id": "group-all", "email": "all@example.com", "name": "Everyone", "description": ""}
    serve(
        connector,
        [{"users": [ADMIN_USER, SUSPENDED_USER]}],
        groups=[GROUP, everyone],
        members={
            "group-1": [{"id": ADMIN_USER["id"], "type": "USER"}],
            "group-all": [{"id": "C00000000", "type": "CUSTOMER"}, {"id": "ext", "type": "EXTERNAL"}],
        },
    )

    admin, suspended = connector.get_assets()

    assert [group.uid for group in admin.user.groups] == ["group-1", "group-all"]
    assert [(group.uid, group.desc) for group in suspended.user.groups] == [("group-all", None)]


def test_get_assets_yields_only_new_or_changed_users(connector):
    serve(connector, [{"users": [ADMIN_USER, SUSPENDED_USER]}])
    list(connector.get_assets())
    connector.update_checkpoint()

    new_user = {**SUSPENDED_USER, "id": "100000000000000000003", "primaryEmail": "new@example.com"}
    logged_in = {**SUSPENDED_USER, "lastLoginTime": "2026-09-29T07:00:00.000Z"}
    serve(connector, [{"users": [ADMIN_USER, logged_in, new_user]}])

    assert [asset.user.uid for asset in connector.get_assets()] == [SUSPENDED_USER["id"], new_user["id"]]


def test_group_membership_change_is_detected(connector):
    serve(connector, [{"users": [ADMIN_USER]}])
    list(connector.get_assets())
    connector.update_checkpoint()

    serve(
        connector,
        [{"users": [ADMIN_USER]}],
        groups=[GROUP],
        members={"group-1": [{"id": ADMIN_USER["id"], "type": "USER"}]},
    )

    assert len(list(connector.get_assets())) == 1


def test_update_checkpoint_drops_deleted_users_only_after_full_listing(connector):
    with connector.context as cache:
        cache[KNOWN_USERS_KEY] = {"deleted-user": "fingerprint"}
    serve(connector, [{"users": [ADMIN_USER], "nextPageToken": "page-2"}, {"users": [SUSPENDED_USER]}])

    assets = connector.get_assets()
    next(assets)
    connector.update_checkpoint()
    with connector.context as cache:
        assert set(cache[KNOWN_USERS_KEY]) == {"deleted-user", ADMIN_USER["id"]}

    list(assets)
    connector.update_checkpoint()
    with connector.context as cache:
        assert set(cache[KNOWN_USERS_KEY]) == {ADMIN_USER["id"], SUSPENDED_USER["id"]}


def test_unchanged_cycle_drops_deleted_users(connector):
    serve(connector, [{"users": [ADMIN_USER]}])
    list(connector.get_assets())
    connector.update_checkpoint()
    with connector.context as cache:
        cache[KNOWN_USERS_KEY] = {**cache[KNOWN_USERS_KEY], "deleted-user": "fingerprint"}

    serve(connector, [{"users": [ADMIN_USER]}])
    assert list(connector.get_assets()) == []

    with connector.context as cache:
        assert set(cache[KNOWN_USERS_KEY]) == {ADMIN_USER["id"]}


def test_unpushed_changes_keep_the_cache(connector):
    with connector.context as cache:
        cache[KNOWN_USERS_KEY] = {"deleted-user": "fingerprint"}
    serve(connector, [{"users": [ADMIN_USER]}])

    assert len(list(connector.get_assets())) == 1

    with connector.context as cache:
        assert cache[KNOWN_USERS_KEY] == {"deleted-user": "fingerprint"}


def test_reset_checkpoint(connector):
    serve(connector, [{"users": [ADMIN_USER]}])
    list(connector.get_assets())
    connector.update_checkpoint()

    connector.reset_checkpoint()

    with connector.context as cache:
        assert KNOWN_USERS_KEY not in cache
    serve(connector, [{"users": [ADMIN_USER]}])
    assert len(list(connector.get_assets())) == 1


def test_get_assets_skips_invalid_user(connector):
    serve(
        connector,
        [
            {
                "users": [
                    {"id": "broken", "creationTime": "2024-01-01T00:00:00Z"},
                    {**ADMIN_USER, "id": "bad-email", "primaryEmail": None},
                    ADMIN_USER,
                ]
            }
        ],
    )

    assets = list(connector.get_assets())

    assert [asset.user.uid for asset in assets] == [ADMIN_USER["id"]]
    assert set(connector._fingerprints) == {ADMIN_USER["id"]}
    connector.log.assert_any_call("Skipping Google Workspace user broken: KeyError('primaryEmail')", level="warning")


def test_get_assets_api_error_keeps_known_users(connector):
    with connector.context as cache:
        cache[KNOWN_USERS_KEY] = {"known-user": "fingerprint"}
    serve(
        connector,
        [
            {"users": [ADMIN_USER], "nextPageToken": "page-2"},
            HttpError(httplib2.Response({"status": 403}), b"forbidden"),
        ],
    )

    assert len(list(connector.get_assets())) == 1
    connector.log_exception.assert_called_once()
    connector.update_checkpoint()
    with connector.context as cache:
        assert set(cache[KNOWN_USERS_KEY]) == {"known-user", ADMIN_USER["id"]}


def test_fetch_cycle_pushes_changes_once(connector):
    serve(connector, [{"users": [ADMIN_USER, SUSPENDED_USER]}])
    connector._http_session = Mock()
    connector._http_session.post.return_value = Mock(status_code=200, json=Mock(return_value={}))

    with patch("sekoia_automation.asset_connector.connector.time.sleep"):
        connector.asset_fetch_cycle()
        assert connector._http_session.post.call_count == 2

        serve(connector, [{"users": [ADMIN_USER, SUSPENDED_USER]}])
        connector.asset_fetch_cycle()
        assert connector._http_session.post.call_count == 2
