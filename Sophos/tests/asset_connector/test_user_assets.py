"""
Unit tests for SophosUserAssetConnector (asset_connector/user_assets.py).
"""

from unittest.mock import MagicMock

import pytest
import requests_mock as req_mock

from sophos_module.asset_connector.model import (
    SophosUser,
    SophosUserGroup,
    SophosUserGroups,
    SophosUserSource,
    SophosTenant,
)
from sophos_module.asset_connector.user_assets import SophosUserAssetConnector, _CACHE_KEY
from sophos_module.base import SophosModule
from sekoia_automation.asset_connector.models.ocsf.user import (
    AccountTypeId,
    AccountTypeStr,
    UserTypeId,
    UserTypeStr,
)

NAMED_USER = SophosUser(
    id="aaaaaaaa-0000-0000-0000-000000000001",
    name="Jane Doe",
    firstName="Jane",
    lastName="Doe",
    email="jane.doe@example.com",
    exchangeLogin="",
    groups=SophosUserGroups(total=0, itemsCount=0, items=[]),
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    source=SophosUserSource(type="custom"),
    createdAt="2023-06-16T15:00:56.473Z",
    updatedAt="2023-06-16T15:00:56.870Z",
)

WINDOWS_USER = SophosUser(
    id="aaaaaaaa-0000-0000-0000-000000000002",
    name="DESKTOP-ABC1234\\jdoe",
    groups=SophosUserGroups(total=0, itemsCount=0, items=[]),
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    source=SophosUserSource(type="custom"),
    createdAt="2025-12-10T12:49:12.371Z",
    updatedAt="2025-12-11T12:22:37.223Z",
)

AD_USER = SophosUser(
    id="aaaaaaaa-0000-0000-0000-000000000005",
    name="test/AC00008700",
    exchangeLogin="AC00008700",
    groups=SophosUserGroups(total=0, itemsCount=0, items=[]),
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    source=SophosUserSource(type="active_directory"),
    createdAt="2024-01-10T08:00:00.000Z",
    updatedAt="2024-01-10T08:00:00.000Z",
)

USER_WITH_GROUPS = SophosUser(
    id="aaaaaaaa-0000-0000-0000-000000000003",
    name="John Smith",
    email="john.smith@example.onmicrosoft.com",
    groups=SophosUserGroups(
        total=1,
        itemsCount=1,
        items=[
            SophosUserGroup(
                id="cccccccc-0000-0000-0000-000000000001",
                name="example.onmicrosoft.com",
                displayName="example.onmicrosoft.com",
            )
        ],
    ),
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    source=SophosUserSource(type="custom"),
    createdAt="2023-11-20T09:46:38.886Z",
)

MINIMAL_USER = SophosUser(
    id="aaaaaaaa-0000-0000-0000-000000000004",
    name="DESKTOP-XYZ5678\\testuser",
    tenant=SophosTenant(id="bbbbbbbb-0000-0000-0000-000000000001"),
    createdAt="2024-10-02T14:32:00.091Z",
    updatedAt="2024-10-02T14:32:01.182Z",
)

# Raw dict versions for HTTP mock tests
NAMED_USER_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "name": "Jane Doe",
    "firstName": "Jane",
    "lastName": "Doe",
    "email": "jane.doe@example.com",
    "exchangeLogin": "",
    "groups": {"total": 0, "itemsCount": 0, "items": []},
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "source": {"type": "custom"},
    "createdAt": "2023-06-16T15:00:56.473Z",
    "updatedAt": "2023-06-16T15:00:56.870Z",
}

WINDOWS_USER_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000002",
    "name": "DESKTOP-ABC1234\\jdoe",
    "groups": {"total": 0, "itemsCount": 0, "items": []},
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "source": {"type": "custom"},
    "createdAt": "2025-12-10T12:49:12.371Z",
    "updatedAt": "2025-12-11T12:22:37.223Z",
}

USER_WITH_GROUPS_DICT = {
    "id": "aaaaaaaa-0000-0000-0000-000000000003",
    "name": "John Smith",
    "email": "john.smith@example.onmicrosoft.com",
    "groups": {
        "total": 1,
        "itemsCount": 1,
        "items": [
            {
                "id": "cccccccc-0000-0000-0000-000000000001",
                "name": "example.onmicrosoft.com",
                "displayName": "example.onmicrosoft.com",
            }
        ],
    },
    "tenant": {"id": "bbbbbbbb-0000-0000-0000-000000000001"},
    "source": {"type": "custom"},
    "createdAt": "2023-11-20T09:46:38.886Z",
}

API_RESPONSE_PAGE1 = {
    "items": [NAMED_USER_DICT, WINDOWS_USER_DICT],
    "pages": {"current": 1, "size": 2, "maxSize": 100},
}

API_RESPONSE_PAGE2 = {
    "items": [USER_WITH_GROUPS_DICT],
    "pages": {"current": 2, "size": 2, "maxSize": 100},
}

AUTH_TOKEN_RESPONSE = {
    "access_token": "test_access_token",
    "refresh_token": "test_refresh_token",
    "token_type": "bearer",
    "message": "OK",
    "errorCode": "success",
    "expires_in": 3600,
}

WHOAMI_RESPONSE = {
    "id": "bbbbbbbb-0000-0000-0000-000000000001",
    "idType": "tenant",
    "apiHosts": {
        "global": "https://api.central.sophos.com",
        "dataRegion": "https://api-eu01.central.sophos.com",
    },
}

AUTH_URL = "https://id.sophos.com/api/v2/oauth2/token"


@pytest.fixture
def connector(symphony_storage):
    module = SophosModule()
    c = SophosUserAssetConnector(module=module, data_path=symphony_storage)
    c.module.configuration = {
        "oauth2_authorization_url": AUTH_URL,
        "api_host": "https://api.central.sophos.com",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }
    c.log = MagicMock()
    c.log_exception = MagicMock()
    type(c).running = property(lambda self: True)
    return c


def _mock_list_users(connector, pages: list[dict]) -> None:
    """Wire connector.client to return successive page responses for users."""
    connector.client = MagicMock()
    responses = []
    for page in pages:
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = page
        responses.append(m)
    connector.client.list_directory_users.side_effect = responses


def _seed_cache(connector, data: dict[str, str]) -> None:
    """Pre-populate the persistent cache with a known_users mapping."""
    with connector.context as cache:
        cache[_CACHE_KEY] = data


class TestGetAccountType:
    def test_local_machine_account_backslash_no_names(self):
        type_id, type_str = SophosUserAssetConnector._get_account_type(WINDOWS_USER)
        assert type_id == AccountTypeId.WINDOWS_ACCOUNT
        assert type_str == AccountTypeStr.WINDOWS_ACCOUNT

    def test_backslash_but_has_first_name_is_not_windows(self):
        """A real named user whose name happens to contain a backslash is not a local account."""
        user = SophosUser(id="x", name="DOMAIN\\user", firstName="John")
        type_id, _ = SophosUserAssetConnector._get_account_type(user)
        assert type_id == AccountTypeId.UNKNOWN

    def test_backslash_but_has_email_is_not_windows(self):
        user = SophosUser(id="x", name="DOMAIN\\user", email="user@example.com")
        type_id, _ = SophosUserAssetConnector._get_account_type(user)
        assert type_id == AccountTypeId.UNKNOWN

    def test_ad_user_with_forward_slash(self):
        type_id, type_str = SophosUserAssetConnector._get_account_type(AD_USER)
        assert type_id == AccountTypeId.LDAP_ACCOUNT
        assert type_str == AccountTypeStr.LDAP_ACCOUNT

    def test_named_user_with_email_is_unknown(self):
        type_id, type_str = SophosUserAssetConnector._get_account_type(NAMED_USER)
        assert type_id == AccountTypeId.UNKNOWN
        assert type_str == AccountTypeStr.UNKNOWN

    def test_forward_slash_but_has_email_is_unknown(self):
        user = SophosUser(id="x", name="DOMAIN/user", email="user@example.com")
        type_id, _ = SophosUserAssetConnector._get_account_type(user)
        assert type_id == AccountTypeId.UNKNOWN

    def test_no_name_is_unknown(self):
        user = SophosUser(id="x", name=None)
        type_id, _ = SophosUserAssetConnector._get_account_type(user)
        assert type_id == AccountTypeId.UNKNOWN


class TestGetUserType:
    def test_named_user_is_user_type(self):
        type_id, type_str = SophosUserAssetConnector._get_user_type(NAMED_USER)
        assert type_id == UserTypeId.USER
        assert type_str == UserTypeStr.USER

    def test_ad_user_is_user_type(self):
        type_id, type_str = SophosUserAssetConnector._get_user_type(AD_USER)
        assert type_id == UserTypeId.USER
        assert type_str == UserTypeStr.USER

    def test_local_machine_account_is_system(self):
        type_id, type_str = SophosUserAssetConnector._get_user_type(WINDOWS_USER)
        assert type_id == UserTypeId.SYSTEM
        assert type_str == UserTypeStr.SYSTEM

    def test_desktop_user_is_local(self):
        assert SophosUserAssetConnector._is_local_machine_account(WINDOWS_USER) is True

    def test_named_user_is_not_local(self):
        assert SophosUserAssetConnector._is_local_machine_account(NAMED_USER) is False

    def test_ad_user_forward_slash_is_not_local(self):
        assert SophosUserAssetConnector._is_local_machine_account(AD_USER) is False

    def test_backslash_with_email_is_not_local(self):
        user = SophosUser(id="x", name="DOMAIN\\user", email="user@example.com")
        assert SophosUserAssetConnector._is_local_machine_account(user) is False

    def test_backslash_with_first_name_is_not_local(self):
        user = SophosUser(id="x", name="DOMAIN\\user", firstName="John")
        assert SophosUserAssetConnector._is_local_machine_account(user) is False


class TestExtractDomain:
    def test_backslash_format(self):
        assert SophosUserAssetConnector._extract_domain("DESKTOP-ABC1234\\jdoe") == "DESKTOP-ABC1234"

    def test_forward_slash_format(self):
        assert SophosUserAssetConnector._extract_domain("URDOM/AC75008715") == "URDOM"

    def test_no_separator_returns_none(self):
        assert SophosUserAssetConnector._extract_domain("Jane Doe") is None

    def test_none_input_returns_none(self):
        assert SophosUserAssetConnector._extract_domain(None) is None

    def test_empty_string_returns_none(self):
        assert SophosUserAssetConnector._extract_domain("") is None


class TestGetGroups:
    def test_user_with_one_group(self):
        groups = SophosUserAssetConnector._get_groups(USER_WITH_GROUPS)
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].uid == "cccccccc-0000-0000-0000-000000000001"
        assert groups[0].name == "example.onmicrosoft.com"

    def test_empty_groups_returns_none(self):
        assert SophosUserAssetConnector._get_groups(NAMED_USER) is None

    def test_missing_groups_returns_none(self):
        user = SophosUser(id="x", name="Test User")
        assert SophosUserAssetConnector._get_groups(user) is None

    def test_group_without_id_is_skipped(self):
        user = SophosUser(
            id="x",
            name="Test",
            groups=SophosUserGroups(
                total=1,
                itemsCount=1,
                items=[SophosUserGroup(id=None, name="no-id-group")],
            ),
        )
        assert SophosUserAssetConnector._get_groups(user) is None


class TestGetOrganization:
    def test_tenant_present(self):
        org = SophosUserAssetConnector._get_organization(NAMED_USER)
        assert org is not None
        assert org.uid == "bbbbbbbb-0000-0000-0000-000000000001"
        assert org.name == "bbbbbbbb-0000-0000-0000-000000000001"

    def test_tenant_missing_returns_none(self):
        user = SophosUser(id="x", name="Test")
        assert SophosUserAssetConnector._get_organization(user) is None

    def test_tenant_empty_id_returns_none(self):
        user = SophosUser(id="x", name="Test", tenant=SophosTenant(id=""))
        assert SophosUserAssetConnector._get_organization(user) is None


class TestParseTs:
    def test_valid_iso(self):
        ts = SophosUserAssetConnector._parse_ts("2023-06-16T15:00:56.473Z")
        assert isinstance(ts, float)
        assert ts > 0

    def test_none_input(self):
        assert SophosUserAssetConnector._parse_ts(None) is None

    def test_empty_string(self):
        assert SophosUserAssetConnector._parse_ts("") is None

    def test_invalid_string(self):
        assert SophosUserAssetConnector._parse_ts("not-a-date") is None


class TestUserTimestamp:
    def test_prefers_updated_at(self):
        ts = SophosUserAssetConnector._user_timestamp(NAMED_USER)
        assert ts == "2023-06-16T15:00:56.870Z"

    def test_falls_back_to_created_at(self):
        user = SophosUser(id="x", name="Test", createdAt="2023-01-01T00:00:00.000Z")
        assert SophosUserAssetConnector._user_timestamp(user) == "2023-01-01T00:00:00.000Z"

    def test_returns_none_when_both_absent(self):
        user = SophosUser(id="x", name="Test")
        assert SophosUserAssetConnector._user_timestamp(user) is None


class TestIsNewOrChanged:
    def test_unknown_user_is_new(self, connector):
        assert connector._is_new_or_changed(NAMED_USER, {}) is True

    def test_unchanged_user_is_skipped(self, connector):
        known = {NAMED_USER.id: "2023-06-16T15:00:56.870Z"}
        assert connector._is_new_or_changed(NAMED_USER, known) is False

    def test_updated_timestamp_triggers_yield(self, connector):
        known = {NAMED_USER.id: "2023-01-01T00:00:00.000Z"}  # older ts
        assert connector._is_new_or_changed(NAMED_USER, known) is True

    def test_user_without_id_is_always_new(self, connector):
        user = SophosUser(id=None, name="ghost")
        assert connector._is_new_or_changed(user, {"anything": "ts"}) is True


class TestMapUserFields:
    def test_named_user_mapping(self, connector):
        result = connector.map_user_fields(NAMED_USER)
        assert result is not None
        assert result.user.uid == "aaaaaaaa-0000-0000-0000-000000000001"
        assert result.user.name == "Jane Doe"
        assert result.user.full_name == "Jane Doe"
        assert result.user.email_addr == "jane.doe@example.com"
        assert result.user.type_id == UserTypeId.USER
        assert result.user.account.type_id == AccountTypeId.UNKNOWN
        assert result.user.org is not None
        assert result.user.org.uid == "bbbbbbbb-0000-0000-0000-000000000001"
        assert result.activity_id == 2
        assert result.class_uid == 5003
        assert result.type_uid == 500302

    def test_windows_user_mapping(self, connector):
        result = connector.map_user_fields(WINDOWS_USER)
        assert result is not None
        assert result.user.account.type_id == AccountTypeId.WINDOWS_ACCOUNT
        assert result.user.type_id == UserTypeId.SYSTEM
        assert result.user.email_addr is None
        assert result.user.full_name is None
        assert result.user.domain == "DESKTOP-ABC1234"

    def test_ad_user_mapping(self, connector):
        result = connector.map_user_fields(AD_USER)
        assert result is not None
        assert result.user.account.type_id == AccountTypeId.LDAP_ACCOUNT
        assert result.user.domain == "test"
        assert result.user.uid_alt == "AC00008700"

    def test_exchange_login_mapped_to_uid_alt(self, connector):
        user = NAMED_USER.model_copy(update={"exchangeLogin": "AC00008700"})
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.user.uid_alt == "AC00008700"

    def test_empty_exchange_login_produces_no_uid_alt(self, connector):
        result = connector.map_user_fields(NAMED_USER)
        assert result is not None
        assert result.user.uid_alt is None

    def test_user_with_groups(self, connector):
        result = connector.map_user_fields(USER_WITH_GROUPS)
        assert result is not None
        assert result.user.groups is not None
        assert len(result.user.groups) == 1

    def test_missing_id_returns_none(self, connector):
        user = NAMED_USER.model_copy(update={"id": None})
        assert connector.map_user_fields(user) is None
        connector.log.assert_called()

    def test_missing_name_returns_none(self, connector):
        user = NAMED_USER.model_copy(update={"name": None})
        assert connector.map_user_fields(user) is None

    def test_event_time_uses_updated_at(self, connector):
        result = connector.map_user_fields(NAMED_USER)
        assert result is not None
        assert result.time == SophosUserAssetConnector._parse_ts("2023-06-16T15:00:56.870Z")

    def test_event_time_falls_back_to_created_at(self, connector):
        user = NAMED_USER.model_copy(update={"updatedAt": None})
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.time == SophosUserAssetConnector._parse_ts("2023-06-16T15:00:56.473Z")

    def test_metadata_product_name(self, connector):
        result = connector.map_user_fields(NAMED_USER)
        assert result is not None
        assert result.metadata.product.name == "Sophos EDR"

    def test_no_tenant_produces_no_org(self, connector):
        user = NAMED_USER.model_copy(update={"tenant": None})
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.user.org is None


class TestFetchAllPages:
    def test_single_page(self, connector):
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        items = list(connector._fetch_all_pages())
        assert len(items) == 2
        connector.client.list_directory_users.assert_called_once()

    def test_include_group_ids_param_is_sent(self, connector):
        _mock_list_users(
            connector,
            [{"items": [NAMED_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        list(connector._fetch_all_pages())
        call_params = connector.client.list_directory_users.call_args[0][0]
        assert call_params.get("includeGroupIds") is True

    def test_multi_page(self, connector):
        _mock_list_users(connector, [API_RESPONSE_PAGE1, API_RESPONSE_PAGE2])
        items = list(connector._fetch_all_pages())
        assert len(items) == 3
        assert connector.client.list_directory_users.call_count == 2
        second_params = connector.client.list_directory_users.call_args_list[1][0][0]
        assert second_params["page"] == 2

    def test_empty_response(self, connector):
        _mock_list_users(
            connector,
            [
                {"items": [], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        assert list(connector._fetch_all_pages()) == []

    def test_stops_when_not_running(self, connector):
        type(connector).running = property(lambda self: False)
        connector.client = MagicMock()
        assert list(connector._fetch_all_pages()) == []
        connector.client.list_directory_users.assert_not_called()


class TestIterUsers:
    def test_first_run_yields_all_users(self, connector):
        """No cache → every user is considered new."""
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        items = list(connector._iter_users())
        assert len(items) == 2

    def test_unchanged_users_are_filtered_out(self, connector):
        """Cache matches current timestamps → nothing yielded."""
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
            },
        )
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        items = list(connector._iter_users())
        assert items == []

    def test_updated_user_is_yielded(self, connector):
        """Cache has old timestamp for one user → only that user is yielded."""
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: "2020-01-01T00:00:00.000Z",  # stale
                WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],  # current
            },
        )
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        items = list(connector._iter_users())
        assert len(items) == 1
        assert items[0].id == NAMED_USER_DICT["id"]

    def test_new_user_is_yielded(self, connector):
        """Cache has one user; second is brand new → only new one yielded."""
        _seed_cache(connector, {NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"]})
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        items = list(connector._iter_users())
        assert len(items) == 1
        assert items[0].id == WINDOWS_USER_DICT["id"]

    def test_current_run_tracks_all_users(self, connector):
        """_current_run is populated for ALL fetched users, not just the yielded ones."""
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],  # unchanged
            },
        )
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        list(connector._iter_users())
        assert NAMED_USER_DICT["id"] in connector._current_run
        assert WINDOWS_USER_DICT["id"] in connector._current_run

    def test_user_without_id_not_tracked_in_current_run(self, connector):
        no_id = {**NAMED_USER_DICT, "id": None}
        _mock_list_users(
            connector,
            [
                {"items": [no_id], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        list(connector._iter_users())
        assert connector._current_run == {}


class TestUpdateCheckpoint:
    def test_saves_current_run_snapshot(self, connector):
        connector._current_run = {
            NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
            WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
        }
        connector.update_checkpoint()
        with connector.context as cache:
            saved = cache.get(_CACHE_KEY, {})
        assert saved[NAMED_USER_DICT["id"]] == NAMED_USER_DICT["updatedAt"]
        assert saved[WINDOWS_USER_DICT["id"]] == WINDOWS_USER_DICT["updatedAt"]

    def test_no_update_when_current_run_empty(self, connector):
        connector.update_checkpoint()  # must not raise
        with connector.context as cache:
            assert cache.get(_CACHE_KEY) is None

    def test_checkpoint_replaces_previous_snapshot(self, connector):
        """Ensure the saved snapshot is the current run (deleted users are evicted)."""
        _seed_cache(connector, {"old-user-id": "2020-01-01T00:00:00.000Z"})
        connector._current_run = {NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"]}
        connector.update_checkpoint()
        with connector.context as cache:
            saved = cache.get(_CACHE_KEY, {})
        assert "old-user-id" not in saved
        assert NAMED_USER_DICT["id"] in saved


class TestGetAssets:
    def test_first_run_yields_all_valid_users(self, connector):
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        assets = list(connector.get_assets())
        assert len(assets) == 2

    def test_desktop_user_domain_in_user(self, connector):
        """Local machine account has its computer name as user.domain."""
        _mock_list_users(
            connector,
            [{"items": [WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        assets = list(connector.get_assets())
        assert len(assets) == 1
        assert assets[0].user.domain == "DESKTOP-ABC1234"
        assert assets[0].user.type_id == UserTypeId.SYSTEM

    def test_second_run_yields_nothing_when_unchanged(self, connector):
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
            },
        )
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        assets = list(connector.get_assets())
        assert assets == []

    def test_second_run_yields_only_changed_user(self, connector):
        updated_windows = {**WINDOWS_USER_DICT, "updatedAt": "2099-01-01T00:00:00.000Z"}
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],  # old ts
            },
        )
        _mock_list_users(
            connector,
            [
                {"items": [NAMED_USER_DICT, updated_windows], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        assets = list(connector.get_assets())
        assert len(assets) == 1
        assert assets[0].user.uid == WINDOWS_USER_DICT["id"]

    def test_skips_users_missing_id(self, connector):
        no_id = {**NAMED_USER_DICT, "id": None}
        _mock_list_users(
            connector,
            [
                {"items": [no_id, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}},
            ],
        )
        assets = list(connector.get_assets())
        assert len(assets) == 1

    def test_raises_on_http_error(self, connector):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        connector.client = MagicMock()
        connector.client.list_directory_users.return_value = mock_response

        with pytest.raises(Exception, match="HTTP 500"):
            list(connector.get_assets())

    def test_update_checkpoint_noop_when_no_data(self, connector):
        connector.update_checkpoint()  # must not raise


class TestFullHttpRoundTrip:
    def test_collect_users_via_http(self, connector):
        data_region = "https://api-eu01.central.sophos.com"

        with req_mock.Mocker() as m:
            m.post(AUTH_URL, json=AUTH_TOKEN_RESPONSE, status_code=200)
            m.get("https://api.central.sophos.com/whoami/v1", json=WHOAMI_RESPONSE, status_code=200)
            m.get(
                f"{data_region}/common/v1/directory/users",
                json={
                    "items": [NAMED_USER_DICT, WINDOWS_USER_DICT],
                    "pages": {"current": 1, "size": 50, "maxSize": 100},
                },
                status_code=200,
            )

            if "client" in connector.__dict__:
                del connector.__dict__["client"]

            assets = list(connector.get_assets())

        assert len(assets) == 2
        names = {a.user.name for a in assets}
        assert "Jane Doe" in names
        assert "DESKTOP-ABC1234\\jdoe" in names


class TestGetMappedFields:
    def test_returns_dict(self, connector):
        result = connector.get_mapped_fields()
        assert isinstance(result, dict)

    def test_is_non_empty(self, connector):
        assert len(connector.get_mapped_fields()) > 0

    def test_all_keys_and_values_are_strings(self, connector):
        mapping = connector.get_mapped_fields()
        for k, v in mapping.items():
            assert isinstance(k, str), f"Key {k!r} is not a string"
            assert isinstance(v, str), f"Value {v!r} is not a string"

    def test_contains_name_mapping(self, connector):
        assert "name" in connector.get_mapped_fields()

    def test_contains_email_mapping(self, connector):
        assert "email" in connector.get_mapped_fields()

    def test_contains_timestamp_mappings(self, connector):
        mapping = connector.get_mapped_fields()
        assert "updatedAt" in mapping
        assert "createdAt" in mapping

    def test_deterministic_across_calls(self, connector):
        assert connector.get_mapped_fields() == connector.get_mapped_fields()

    def test_values_reference_user_namespace_or_time(self, connector):
        """All OCSF paths must point into the user object or top-level time field."""
        for v in connector.get_mapped_fields().values():
            assert v.startswith("user.") or v == "time", (
                f"Expected OCSF path to start with 'user.' or be 'time', got {v!r}"
            )


class TestResetCheckpoint:
    def test_clears_known_users_from_context(self, connector):
        _seed_cache(connector, {NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"]})

        connector.reset_checkpoint()

        with connector.context as cache:
            assert cache.get(_CACHE_KEY) is None

    def test_resets_current_run_in_memory(self, connector):
        connector._current_run = {NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"]}
        connector.reset_checkpoint()
        assert connector._current_run == {}

    def test_logs_info_message(self, connector):
        connector.reset_checkpoint()
        log_calls = [str(call) for call in connector.log.call_args_list]
        assert any("reset" in call.lower() for call in log_calls)

    def test_noop_on_empty_context(self, connector):
        """reset_checkpoint must not raise when the context is already empty."""
        connector.reset_checkpoint()  # must not raise

    def test_full_refetch_after_reset(self, connector):
        """After reset, the next get_assets() run must re-yield all users."""
        _mock_list_users(
            connector,
            [{"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        list(connector.get_assets())  # seeds cache

        connector.reset_checkpoint()

        _mock_list_users(
            connector,
            [{"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        assets = list(connector.get_assets())
        assert len(assets) == 2

    def test_second_run_after_reset_treats_all_as_new(self, connector):
        """A reset must make _is_new_or_changed return True for every user."""
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
            },
        )
        # Without reset, second run should yield nothing
        _mock_list_users(
            connector,
            [{"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        no_changes = list(connector.get_assets())
        assert no_changes == []

        connector.reset_checkpoint()

        _mock_list_users(
            connector,
            [{"items": [NAMED_USER_DICT, WINDOWS_USER_DICT], "pages": {"current": 1, "size": 50, "maxSize": 100}}],
        )
        after_reset = list(connector.get_assets())
        assert len(after_reset) == 2
