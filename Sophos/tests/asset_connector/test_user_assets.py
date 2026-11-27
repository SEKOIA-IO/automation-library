"""
Unit tests for SophosUserAssetConnector (asset_connector/user_assets.py).
"""

import logging
from unittest.mock import MagicMock

import pytest
import requests_mock as req_mock
from sekoia_automation.asset_connector.models.ocsf.user import (
    AccountTypeId,
    AccountTypeStr,
    UserTypeId,
    UserTypeStr,
)

from sophos_module.asset_connector.model import (
    SophosTenant,
    SophosUser,
    SophosUserGroup,
    SophosUserGroups,
    SophosUserSource,
)
from sophos_module.asset_connector.user_assets import _CACHE_KEY, SophosUserAssetConnector
from sophos_module.base import SophosModule

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


def _page(*items: dict) -> dict:
    """Build a single-page API response containing the given raw users."""
    return {"items": list(items), "pages": {"current": 1, "size": 50, "maxSize": 100}}


class TestGetAccountType:
    @pytest.mark.parametrize(
        ("user", "expected_id", "expected_str"),
        [
            pytest.param(
                WINDOWS_USER,
                AccountTypeId.WINDOWS_ACCOUNT,
                AccountTypeStr.WINDOWS_ACCOUNT,
                id="local_machine_account_backslash_no_names",
            ),
            # A real named user whose name happens to contain a backslash is not a local account.
            pytest.param(
                SophosUser(id="x", name="DOMAIN\\user", firstName="John"),
                AccountTypeId.UNKNOWN,
                AccountTypeStr.UNKNOWN,
                id="backslash_but_has_first_name_is_not_windows",
            ),
            pytest.param(
                SophosUser(id="x", name="DOMAIN\\user", email="user@example.com"),
                AccountTypeId.UNKNOWN,
                AccountTypeStr.UNKNOWN,
                id="backslash_but_has_email_is_not_windows",
            ),
            pytest.param(
                AD_USER, AccountTypeId.LDAP_ACCOUNT, AccountTypeStr.LDAP_ACCOUNT, id="ad_user_with_forward_slash"
            ),
            pytest.param(
                NAMED_USER, AccountTypeId.UNKNOWN, AccountTypeStr.UNKNOWN, id="named_user_with_email_is_unknown"
            ),
            pytest.param(
                SophosUser(id="x", name="DOMAIN/user", email="user@example.com"),
                AccountTypeId.UNKNOWN,
                AccountTypeStr.UNKNOWN,
                id="forward_slash_but_has_email_is_unknown",
            ),
            pytest.param(
                SophosUser(id="x", name=None), AccountTypeId.UNKNOWN, AccountTypeStr.UNKNOWN, id="no_name_is_unknown"
            ),
        ],
    )
    def test_get_account_type(self, user, expected_id, expected_str):
        type_id, type_str = SophosUserAssetConnector._get_account_type(user)
        assert type_id == expected_id
        assert type_str == expected_str


class TestGetUserType:
    @pytest.mark.parametrize(
        ("user", "expected_id", "expected_str"),
        [
            pytest.param(NAMED_USER, UserTypeId.USER, UserTypeStr.USER, id="named_user_is_user_type"),
            pytest.param(AD_USER, UserTypeId.USER, UserTypeStr.USER, id="ad_user_is_user_type"),
            pytest.param(WINDOWS_USER, UserTypeId.SYSTEM, UserTypeStr.SYSTEM, id="local_machine_account_is_system"),
        ],
    )
    def test_get_user_type(self, user, expected_id, expected_str):
        type_id, type_str = SophosUserAssetConnector._get_user_type(user)
        assert type_id == expected_id
        assert type_str == expected_str

    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            pytest.param(WINDOWS_USER, True, id="desktop_user_is_local"),
            pytest.param(NAMED_USER, False, id="named_user_is_not_local"),
            pytest.param(AD_USER, False, id="ad_user_forward_slash_is_not_local"),
            pytest.param(
                SophosUser(id="x", name="DOMAIN\\user", email="user@example.com"),
                False,
                id="backslash_with_email_is_not_local",
            ),
            pytest.param(
                SophosUser(id="x", name="DOMAIN\\user", firstName="John"),
                False,
                id="backslash_with_first_name_is_not_local",
            ),
        ],
    )
    def test_is_local_machine_account(self, user, expected):
        assert SophosUserAssetConnector._is_local_machine_account(user) is expected


class TestExtractDomain:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            pytest.param("DESKTOP-ABC1234\\jdoe", "DESKTOP-ABC1234", id="backslash_format"),
            pytest.param("URDOM/AC75008715", "URDOM", id="forward_slash_format"),
            pytest.param("Jane Doe", None, id="no_separator_returns_none"),
            pytest.param(None, None, id="none_input_returns_none"),
            pytest.param("", None, id="empty_string_returns_none"),
        ],
    )
    def test_extract_domain(self, name, expected):
        assert SophosUserAssetConnector._extract_domain(name) == expected


class TestExtractLogin:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            pytest.param("CORP\\jdoe", "jdoe", id="backslash_format"),
            pytest.param("CORP/jdoe", "jdoe", id="forward_slash_format"),
            pytest.param("jdoe", "jdoe", id="no_separator"),
            pytest.param("Jane Doe", "Jane Doe", id="display_name_without_separator"),
            pytest.param("CORP\\", "CORP\\", id="empty_login_after_separator_keeps_name"),
        ],
    )
    def test_extract_login(self, name, expected):
        assert SophosUserAssetConnector._extract_login(name) == expected


class TestGetGroups:
    def test_user_with_one_group(self):
        groups = SophosUserAssetConnector._get_groups(USER_WITH_GROUPS)
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].uid == "cccccccc-0000-0000-0000-000000000001"
        assert groups[0].name == "example.onmicrosoft.com"

    @pytest.mark.parametrize(
        "user",
        [
            pytest.param(NAMED_USER, id="empty_groups_returns_none"),
            pytest.param(SophosUser(id="x", name="Test User"), id="missing_groups_returns_none"),
            pytest.param(
                SophosUser(
                    id="x",
                    name="Test",
                    groups=SophosUserGroups(
                        total=1,
                        itemsCount=1,
                        items=[SophosUserGroup(id=None, name="no-id-group")],
                    ),
                ),
                id="group_without_id_is_skipped",
            ),
        ],
    )
    def test_no_usable_groups_returns_none(self, user):
        assert SophosUserAssetConnector._get_groups(user) is None


class TestGetOrganization:
    def test_tenant_present(self):
        org = SophosUserAssetConnector._get_organization(NAMED_USER)
        assert org is not None
        assert org.uid == "bbbbbbbb-0000-0000-0000-000000000001"
        assert org.name == "bbbbbbbb-0000-0000-0000-000000000001"

    @pytest.mark.parametrize(
        "user",
        [
            pytest.param(SophosUser(id="x", name="Test"), id="tenant_missing_returns_none"),
            pytest.param(
                SophosUser(id="x", name="Test", tenant=SophosTenant(id="")), id="tenant_empty_id_returns_none"
            ),
        ],
    )
    def test_no_tenant_id_returns_none(self, user):
        assert SophosUserAssetConnector._get_organization(user) is None


class TestParseTs:
    def test_valid_iso(self):
        ts = SophosUserAssetConnector._parse_ts("2023-06-16T15:00:56.473Z")
        assert isinstance(ts, float)
        assert ts > 0

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(None, id="none_input"),
            pytest.param("", id="empty_string"),
            pytest.param("not-a-date", id="invalid_string"),
        ],
    )
    def test_unparsable_returns_none(self, value):
        assert SophosUserAssetConnector._parse_ts(value) is None


class TestUserTimestamp:
    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            pytest.param(NAMED_USER, "2023-06-16T15:00:56.870Z", id="prefers_updated_at"),
            pytest.param(
                SophosUser(id="x", name="Test", createdAt="2023-01-01T00:00:00.000Z"),
                "2023-01-01T00:00:00.000Z",
                id="falls_back_to_created_at",
            ),
            pytest.param(SophosUser(id="x", name="Test"), None, id="returns_none_when_both_absent"),
        ],
    )
    def test_user_timestamp(self, user, expected):
        assert SophosUserAssetConnector._user_timestamp(user) == expected


class TestIsNewOrChanged:
    @pytest.mark.parametrize(
        ("user", "known", "expected"),
        [
            pytest.param(NAMED_USER, {}, True, id="unknown_user_is_new"),
            pytest.param(
                NAMED_USER, {NAMED_USER.id: "2023-06-16T15:00:56.870Z"}, False, id="unchanged_user_is_skipped"
            ),
            pytest.param(
                NAMED_USER,
                {NAMED_USER.id: "2023-01-01T00:00:00.000Z"},  # older ts
                True,
                id="updated_timestamp_triggers_yield",
            ),
            pytest.param(
                SophosUser(id=None, name="ghost"), {"anything": "ts"}, True, id="user_without_id_is_always_new"
            ),
        ],
    )
    def test_is_new_or_changed(self, connector, user, known, expected):
        assert connector._is_new_or_changed(user, known) is expected


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
        assert result.user.name == WINDOWS_USER.name
        assert result.user.account.name == WINDOWS_USER.name

    def test_ad_user_mapping(self, connector):
        result = connector.map_user_fields(AD_USER)
        assert result is not None
        assert result.user.account.type_id == AccountTypeId.LDAP_ACCOUNT
        assert result.user.domain == "test"
        assert result.user.uid_alt == "AC00008700"
        assert result.user.name == AD_USER.name.split("/", 1)[1]
        assert result.user.account.name == result.user.name

    @pytest.mark.parametrize(
        "user",
        [
            pytest.param(
                WINDOWS_USER.model_copy(
                    update={"name": "CORP\\jdoe", "source": SophosUserSource(type="active_directory")}
                ),
                id="active_directory_user_without_email_or_names_is_sent_without_its_domain",
            ),
            pytest.param(
                NAMED_USER.model_copy(update={"name": "CORP\\jdoe"}),
                id="domain_user_with_a_backslash_is_sent_without_its_domain",
            ),
        ],
    )
    def test_backslash_user_is_sent_without_its_domain(self, connector, user):
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.user.name == "jdoe"
        assert result.user.account.name == "jdoe"
        assert result.user.domain == "CORP"
        assert result.user.type_id == UserTypeId.USER

    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            pytest.param(
                NAMED_USER.model_copy(update={"exchangeLogin": "AC00008700"}),
                "AC00008700",
                id="exchange_login_mapped_to_uid_alt",
            ),
            pytest.param(NAMED_USER, None, id="empty_exchange_login_produces_no_uid_alt"),
        ],
    )
    def test_uid_alt(self, connector, user, expected):
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.user.uid_alt == expected

    def test_user_with_groups(self, connector):
        result = connector.map_user_fields(USER_WITH_GROUPS)
        assert result is not None
        assert result.user.groups is not None
        assert len(result.user.groups) == 1

    @pytest.mark.parametrize(
        "user",
        [
            pytest.param(NAMED_USER.model_copy(update={"id": None}), id="missing_id_returns_none"),
            pytest.param(NAMED_USER.model_copy(update={"name": None}), id="missing_name_returns_none"),
        ],
    )
    def test_missing_mandatory_field_returns_none(self, connector, caplog, user):
        caplog.set_level(logging.DEBUG)
        assert connector.map_user_fields(user) is None
        # one warning per skipped user: pod logs only, the user sees the skipped count of the run
        connector.log.assert_not_called()
        assert any("Skipping user: missing" in record.getMessage() for record in caplog.records)

    @pytest.mark.parametrize(
        ("user", "expected_ts"),
        [
            pytest.param(NAMED_USER, "2023-06-16T15:00:56.870Z", id="uses_updated_at"),
            pytest.param(
                NAMED_USER.model_copy(update={"updatedAt": None}),
                "2023-06-16T15:00:56.473Z",
                id="falls_back_to_created_at",
            ),
        ],
    )
    def test_event_time(self, connector, user, expected_ts):
        result = connector.map_user_fields(user)
        assert result is not None
        assert result.time == SophosUserAssetConnector._parse_ts(expected_ts)

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
    @pytest.mark.parametrize(
        ("page", "expected_ids"),
        [
            pytest.param(
                _page(NAMED_USER_DICT, WINDOWS_USER_DICT),
                [NAMED_USER_DICT["id"], WINDOWS_USER_DICT["id"]],
                id="single_page",
            ),
            pytest.param(_page(), [], id="empty_response"),
        ],
    )
    def test_single_partial_page(self, connector, page, expected_ids):
        _mock_list_users(connector, [page])
        items = list(connector._fetch_all_pages())
        assert [item.id for item in items] == expected_ids
        connector.client.list_directory_users.assert_called_once()

    def test_include_group_ids_param_is_sent(self, connector):
        _mock_list_users(connector, [_page(NAMED_USER_DICT)])
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

    def test_stops_when_not_running(self, connector):
        type(connector).running = property(lambda self: False)
        connector.client = MagicMock()
        assert list(connector._fetch_all_pages()) == []
        connector.client.list_directory_users.assert_not_called()


class TestIterUsers:
    @pytest.mark.parametrize(
        ("cache", "expected_ids"),
        [
            # No cache → every user is considered new.
            pytest.param(
                None,
                [NAMED_USER_DICT["id"], WINDOWS_USER_DICT["id"]],
                id="first_run_yields_all_users",
            ),
            # Cache matches current timestamps → nothing yielded.
            pytest.param(
                {
                    NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                    WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
                },
                [],
                id="unchanged_users_are_filtered_out",
            ),
            # Cache has old timestamp for one user → only that user is yielded.
            pytest.param(
                {
                    NAMED_USER_DICT["id"]: "2020-01-01T00:00:00.000Z",  # stale
                    WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],  # current
                },
                [NAMED_USER_DICT["id"]],
                id="updated_user_is_yielded",
            ),
            # Cache has one user; second is brand new → only new one yielded.
            pytest.param(
                {NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"]},
                [WINDOWS_USER_DICT["id"]],
                id="new_user_is_yielded",
            ),
        ],
    )
    def test_yields_new_or_changed_users(self, connector, cache, expected_ids):
        if cache is not None:
            _seed_cache(connector, cache)
        _mock_list_users(connector, [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)])
        items = list(connector._iter_users())
        assert [item.id for item in items] == expected_ids

    def test_current_run_tracks_all_users(self, connector):
        """_current_run is populated for ALL fetched users, not just the yielded ones."""
        _seed_cache(
            connector,
            {
                NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],  # unchanged
            },
        )
        _mock_list_users(connector, [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)])
        list(connector._iter_users())
        assert NAMED_USER_DICT["id"] in connector._current_run
        assert WINDOWS_USER_DICT["id"] in connector._current_run

    def test_user_without_id_not_tracked_in_current_run(self, connector):
        no_id = {**NAMED_USER_DICT, "id": None}
        _mock_list_users(connector, [_page(no_id)])
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
    @pytest.mark.parametrize(
        ("cache", "items", "expected_uids"),
        [
            pytest.param(
                None,
                [NAMED_USER_DICT, WINDOWS_USER_DICT],
                [NAMED_USER_DICT["id"], WINDOWS_USER_DICT["id"]],
                id="first_run_yields_all_valid_users",
            ),
            pytest.param(
                {
                    NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                    WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],
                },
                [NAMED_USER_DICT, WINDOWS_USER_DICT],
                [],
                id="second_run_yields_nothing_when_unchanged",
            ),
            pytest.param(
                {
                    NAMED_USER_DICT["id"]: NAMED_USER_DICT["updatedAt"],
                    WINDOWS_USER_DICT["id"]: WINDOWS_USER_DICT["updatedAt"],  # old ts
                },
                [NAMED_USER_DICT, {**WINDOWS_USER_DICT, "updatedAt": "2099-01-01T00:00:00.000Z"}],
                [WINDOWS_USER_DICT["id"]],
                id="second_run_yields_only_changed_user",
            ),
            pytest.param(
                None,
                [{**NAMED_USER_DICT, "id": None}, WINDOWS_USER_DICT],
                [WINDOWS_USER_DICT["id"]],
                id="skips_users_missing_id",
            ),
        ],
    )
    def test_yields_mapped_new_or_changed_users(self, connector, cache, items, expected_uids):
        if cache is not None:
            _seed_cache(connector, cache)
        _mock_list_users(connector, [_page(*items)])
        assets = list(connector.get_assets())
        assert [asset.user.uid for asset in assets] == expected_uids

    def test_desktop_user_domain_in_user(self, connector):
        """Local machine account has its computer name as user.domain."""
        _mock_list_users(connector, [_page(WINDOWS_USER_DICT)])
        assets = list(connector.get_assets())
        assert len(assets) == 1
        assert assets[0].user.domain == "DESKTOP-ABC1234"
        assert assets[0].user.type_id == UserTypeId.SYSTEM

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
                json=_page(NAMED_USER_DICT, WINDOWS_USER_DICT),
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

    def test_declares_the_domain_prefix(self, connector):
        assert connector.get_mapped_fields()["name (domain prefix)"] == "user.domain"

    def test_is_non_empty(self, connector):
        assert len(connector.get_mapped_fields()) > 0

    def test_all_keys_and_values_are_strings(self, connector):
        mapping = connector.get_mapped_fields()
        for k, v in mapping.items():
            assert isinstance(k, str), f"Key {k!r} is not a string"
            assert isinstance(v, str), f"Value {v!r} is not a string"

    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("name", id="contains_name_mapping"),
            pytest.param("email", id="contains_email_mapping"),
            pytest.param("updatedAt", id="contains_updated_at_mapping"),
            pytest.param("createdAt", id="contains_created_at_mapping"),
        ],
    )
    def test_contains_mapping(self, connector, key):
        assert key in connector.get_mapped_fields()

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
            [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)],
        )
        list(connector.get_assets())  # seeds cache

        connector.reset_checkpoint()

        _mock_list_users(
            connector,
            [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)],
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
            [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)],
        )
        no_changes = list(connector.get_assets())
        assert no_changes == []

        connector.reset_checkpoint()

        _mock_list_users(
            connector,
            [_page(NAMED_USER_DICT, WINDOWS_USER_DICT)],
        )
        after_reset = list(connector.get_assets())
        assert len(after_reset) == 2
