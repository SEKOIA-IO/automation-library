import pytest
from datetime import datetime
from unittest.mock import Mock

from crowdstrike_falcon.asset_connectors.user_assets import CrowdstrikeUserAssetConnector
from crowdstrike_falcon.client import CrowdstrikeFalconClient
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserOCSFModel,
    AccountTypeId,
    AccountTypeStr,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr


class _DummyContext(dict):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def connector():
    class FakeModule:
        class configuration:
            base_url = "https://api.crowdstrike.com"
            client_id = "fake_client_id"
            client_secret = "fake_client_secret"

        manifest = {"slug": "crowdstrike-falcon", "version": "1.0.0"}

    c = CrowdstrikeUserAssetConnector(module=FakeModule())
    c.context = _DummyContext()
    c.log = Mock()
    c.log_exception = Mock()
    return c

@pytest.fixture
def client():
    return CrowdstrikeFalconClient(
        base_url="https://api.crowdstrike.com",
        client_id="fake_client_id",
        client_secret="fake_client_secret",
    )

class TestMapRiskLevel:
    def test_map_risk_level_critical(self, connector):
        result = connector._map_risk_level("CRITICAL")
        assert result == (RiskLevelId.CRITICAL, RiskLevelStr.CRITICAL)

    def test_map_risk_level_high(self, connector):
        result = connector._map_risk_level("HIGH")
        assert result == (RiskLevelId.HIGH, RiskLevelStr.HIGH)

    def test_map_risk_level_medium(self, connector):
        result = connector._map_risk_level("MEDIUM")
        assert result == (RiskLevelId.MEDIUM, RiskLevelStr.MEDIUM)

    def test_map_risk_level_low(self, connector):
        result = connector._map_risk_level("LOW")
        assert result == (RiskLevelId.LOW, RiskLevelStr.LOW)

    def test_map_risk_level_info(self, connector):
        result = connector._map_risk_level("INFO")
        assert result == (RiskLevelId.INFO, RiskLevelStr.INFO)

    def test_map_risk_level_none(self, connector):
        result = connector._map_risk_level(None)
        assert result == (None, None)

    def test_map_risk_level_unknown(self, connector):
        result = connector._map_risk_level("UNKNOWN_VALUE")
        assert result == (None, None)


class TestDetermineAccountType:
    def test_active_directory_by_datasource(self, connector):
        account = {"dataSource": "ACTIVE_DIRECTORY"}
        result = connector._determine_account_type(account)
        assert result == (AccountTypeId.LDAP_ACCOUNT, AccountTypeStr.LDAP_ACCOUNT)

    def test_active_directory_by_object_sid(self, connector):
        account = {"dataSource": "OTHER", "objectSid": "S-1-5-21-123"}
        result = connector._determine_account_type(account)
        assert result == (AccountTypeId.LDAP_ACCOUNT, AccountTypeStr.LDAP_ACCOUNT)

    def test_azure_account(self, connector):
        account = {"dataSource": "AZURE_AD"}
        result = connector._determine_account_type(account)
        assert result == (AccountTypeId.AZURE_AD_ACCOUNT, AccountTypeStr.AZURE_AD_ACCOUNT)

    def test_other_account(self, connector):
        account = {"dataSource": "UNKNOWN_SOURCE"}
        result = connector._determine_account_type(account)
        assert result == (AccountTypeId.OTHER, AccountTypeStr.OTHER)


class TestDetermineUserType:
    def test_admin_user(self, connector):
        entity = {"roles": [{"type": "ADMIN"}]}
        result = connector._determine_user_type(entity)
        assert result == (UserTypeId.ADMIN, UserTypeStr.ADMIN)

    def test_regular_user(self, connector):
        entity = {"roles": [{"type": "USER"}]}
        result = connector._determine_user_type(entity)
        assert result == (UserTypeId.USER, UserTypeStr.USER)

    def test_no_roles(self, connector):
        entity = {"roles": []}
        result = connector._determine_user_type(entity)
        assert result == (UserTypeId.USER, UserTypeStr.USER)

    def test_missing_roles(self, connector):
        entity = {}
        result = connector._determine_user_type(entity)
        assert result == (UserTypeId.USER, UserTypeStr.USER)


class TestMapIdentityEntityFields:
    def test_map_identity_entity_fields_happy_path(self, connector):
        entity = {
            "entityId": "entity-123",
            "primaryDisplayName": "Alice Smith",
            "secondaryDisplayName": "alice.smith",
            "emailAddresses": ["alice@example.com"],
            "creationTime": "2025-01-01T12:00:00Z",
            "riskScore": 0.66,
            "riskScoreSeverity": "MEDIUM",
            "accounts": [
                {
                    "dataSource": "ACTIVE_DIRECTORY",
                    "domain": "CORP",
                    "samAccountName": "asmith",
                    "objectSid": "S-1-5-21-123",
                    "enabled": True,
                }
            ],
            "roles": [{"type": "USER"}],
        }

        result = connector.map_identity_entity_fields(entity)

        assert isinstance(result, UserOCSFModel)
        assert result.user.name == "Alice Smith"
        assert result.user.uid == "entity-123"
        assert result.user.email_addr == "alice@example.com"
        assert result.user.full_name == "Alice Smith alice.smith"
        assert result.user.domain == "CORP"
        assert result.user.risk_score == 66
        assert result.user.risk_level_id == RiskLevelId.MEDIUM
        assert result.user.risk_level == RiskLevelStr.MEDIUM
        assert result.user.type_id == UserTypeId.USER
        assert result.user.account.name == "asmith"
        assert result.user.account.type_id == AccountTypeId.LDAP_ACCOUNT
        assert result.user.account.uid == "S-1-5-21-123"
        assert result.time == int(datetime.fromisoformat("2025-01-01T12:00:00+00:00").timestamp())
        assert result.enrichments[0].data.is_enabled is True

    def test_map_identity_entity_fields_minimal(self, connector):
        entity = {
            "entityId": "entity-456",
            "primaryDisplayName": "Bob",
        }

        result = connector.map_identity_entity_fields(entity)

        assert result.user.name == "Bob"
        assert result.user.uid == "entity-456"
        assert result.user.email_addr is None
        assert result.user.account is None
        assert result.user.risk_score == 0
        assert result.time == 0
        assert result.enrichments is None

    def test_map_identity_entity_fields_risk_score_conversion(self, connector):
        """Test que le risk_score float (0-1) est converti en int (0-100)."""
        test_cases = [
            (0.0, 0),
            (0.5, 50),
            (0.66, 66),
            (1.0, 100),
            (None, 0),
        ]
        for input_score, expected_score in test_cases:
            entity = {"entityId": "test", "primaryDisplayName": "Test", "riskScore": input_score}
            result = connector.map_identity_entity_fields(entity)
            assert result.user.risk_score == expected_score

    def test_map_identity_entity_fields_admin_role(self, connector):
        entity = {
            "entityId": "admin-123",
            "primaryDisplayName": "Admin User",
            "roles": [{"type": "ADMIN"}],
        }

        result = connector.map_identity_entity_fields(entity)

        assert result.user.type_id == UserTypeId.ADMIN
        assert result.user.type == UserTypeStr.ADMIN


class TestCheckpoint:
    def test_most_recent_user_date_returns_cached_value(self, connector):
        connector.context["user_assets_last_seen_timestamp"] = "2025-01-15T10:00:00Z"
        assert connector.most_recent_user_date == "2025-01-15T10:00:00Z"

    def test_most_recent_user_date_returns_none_when_empty(self, connector):
        assert connector.most_recent_user_date is None

    def test_update_checkpoint_saves_latest_time(self, connector):
        connector._latest_time = "2025-06-01T12:00:00Z"
        connector.update_checkpoint()
        assert connector.context["most_recent_date_seen"] == "2025-06-01T12:00:00Z"

    def test_update_checkpoint_does_nothing_when_latest_time_is_none(self, connector):
        connector.context["most_recent_date_seen"] = "2025-01-01T00:00:00Z"
        connector._latest_time = None
        connector.update_checkpoint()
        assert connector.context["most_recent_date_seen"] == "2025-01-01T00:00:00Z"
        connector.log.assert_called_with(
            "Warning: new_most_recent_date is None, skipping checkpoint update", level="warning"
        )

    def test_update_checkpoint_handles_exception(self, connector):
        connector._latest_time = "2025-06-01T12:00:00Z"
        connector.context = Mock()
        connector.context.__enter__ = Mock(side_effect=Exception("Storage error"))
        connector.context.__exit__ = Mock(return_value=False)

        connector.update_checkpoint()

        connector.log.assert_any_call("Failed to update checkpoint: Storage error", level="error")

    def test_checkpoint_update_after_fetching_entities(self, connector):
        entities = [
            {"entityId": "1", "creationTime": "2025-01-01T10:00:00Z"},
            {"entityId": "2", "creationTime": "2025-01-03T10:00:00Z"},
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        list(connector._fetch_identity_entities())
        connector.update_checkpoint()

        assert connector.context["most_recent_date_seen"] == "2025-01-03T10:00:00Z"


class TestFetchIdentityEntities:
    def test_fetch_identity_entities_without_checkpoint(self, connector):
        entities = [
            {"entityId": "1", "creationTime": "2025-01-01T10:00:00Z"},
            {"entityId": "2", "creationTime": "2025-01-02T10:00:00Z"},
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        result = list(connector._fetch_identity_entities())

        assert len(result) == 2
        assert connector._latest_time == "2025-01-02T10:00:00Z"

    def test_fetch_identity_entities_with_checkpoint_filters_old(self, connector):
        connector.context["user_assets_last_seen_timestamp"] = "2025-01-01T12:00:00Z"
        entities = [
            {"entityId": "1", "creationTime": "2025-01-01T10:00:00Z"},  # Avant checkpoint
            {"entityId": "2", "creationTime": "2025-01-02T10:00:00Z"},  # Après checkpoint
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        result = list(connector._fetch_identity_entities())

        assert len(result) == 1
        assert result[0]["entityId"] == "2"
        assert connector._latest_time == "2025-01-02T10:00:00Z"

    def test_fetch_identity_entities_updates_checkpoint_on_new_data(self, connector):
        entities = [
            {"entityId": "1", "creationTime": "2025-01-01T10:00:00Z"},
            {"entityId": "2", "creationTime": "2025-01-03T10:00:00Z"},
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        list(connector._fetch_identity_entities())

        assert connector.context["most_recent_date_seen"] == "2025-01-03T10:00:00Z"

    def test_fetch_identity_entities_no_checkpoint_update_when_no_new_data(self, connector):
        connector.context["user_assets_last_seen_timestamp"] = "2025-01-05T00:00:00Z"
        entities = [
            {"entityId": "1", "creationTime": "2025-01-01T10:00:00Z"},
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        result = list(connector._fetch_identity_entities())

        assert result == []
        assert "most_recent_date_seen" not in connector.context


class TestGetAssets:
    def test_get_assets_yields_mapped_models(self, connector):
        entities = [
            {"entityId": "1", "primaryDisplayName": "User1", "creationTime": "2025-01-01T10:00:00Z"},
            {"entityId": "2", "primaryDisplayName": "User2", "creationTime": "2025-01-02T10:00:00Z"},
        ]
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter(entities)

        assets = list(connector.get_assets())

        assert len(assets) == 2
        assert all(isinstance(asset, UserOCSFModel) for asset in assets)
        assert assets[0].user.uid == "1"
        assert assets[1].user.uid == "2"
        connector.log.assert_called()

    def test_get_assets_empty_when_no_entities(self, connector):
        connector.client = Mock()
        connector.client.list_identity_entities.return_value = iter([])

        assets = list(connector.get_assets())

        assert assets == []


class TestParseTimestamp:
    def test_parse_timestamp_with_z_suffix(self, connector):
        """Test parsing timestamp with Z suffix."""
        result = connector._parse_timestamp("2025-01-01T12:00:00Z")
        expected = int(datetime.fromisoformat("2025-01-01T12:00:00+00:00").timestamp())
        assert result == expected

    def test_parse_timestamp_with_explicit_utc_offset(self, connector):
        """Test parsing timestamp with explicit +00:00 offset."""
        result = connector._parse_timestamp("2025-01-01T12:00:00+00:00")
        expected = int(datetime.fromisoformat("2025-01-01T12:00:00+00:00").timestamp())
        assert result == expected

    def test_parse_timestamp_with_positive_offset(self, connector):
        """Test parsing timestamp with positive timezone offset."""
        result = connector._parse_timestamp("2025-01-01T12:00:00+01:00")
        expected = int(datetime.fromisoformat("2025-01-01T12:00:00+01:00").timestamp())
        assert result == expected

    def test_parse_timestamp_with_negative_offset(self, connector):
        """Test parsing timestamp with negative timezone offset."""
        result = connector._parse_timestamp("2025-01-01T12:00:00-05:00")
        expected = int(datetime.fromisoformat("2025-01-01T12:00:00-05:00").timestamp())
        assert result == expected

    def test_parse_timestamp_none(self, connector):
        """Test parsing None returns 0."""
        result = connector._parse_timestamp(None)
        assert result == 0

    def test_parse_timestamp_empty_string(self, connector):
        """Test parsing empty string returns 0."""
        result = connector._parse_timestamp("")
        assert result == 0

    def test_parse_timestamp_invalid_format(self, connector):
        """Test parsing invalid format returns 0."""
        result = connector._parse_timestamp("invalid-date")
        assert result == 0

    def test_parse_timestamp_partial_date(self, connector):
        """Test parsing partial date returns 0."""
        result = connector._parse_timestamp("2025-01-01")
        assert isinstance(result, int)

    def test_parse_timestamp_malformed_iso(self, connector):
        """Test parsing malformed ISO string returns 0."""
        result = connector._parse_timestamp("2025/01/01T12:00:00Z")
        assert result == 0

    def test_parse_timestamp_with_microseconds(self, connector):
        """Test parsing timestamp with microseconds."""
        result = connector._parse_timestamp("2025-01-01T12:00:00.123456Z")
        expected = int(datetime.fromisoformat("2025-01-01T12:00:00.123456+00:00").timestamp())
        assert result == expected


class TestListIdentityEntities:
    def test_list_identity_entities_single_page(self, client):
        entities = [
            {"entityId": "1", "primaryDisplayName": "User1"},
            {"entityId": "2", "primaryDisplayName": "User2"},
        ]
        client.request_graphql_endpoint = Mock(return_value=iter(entities))

        result = list(client.list_identity_entities("query { test }"))

        assert len(result) == 2
        assert result[0]["entityId"] == "1"
        assert result[1]["entityId"] == "2"
        client.request_graphql_endpoint.assert_called_once()

    def test_list_identity_entities_multiple_pages(self, client):
        entities = [
            {"entityId": "1"},
            {"entityId": "2"},
        ]
        client.request_graphql_endpoint = Mock(return_value=iter(entities))

        result = list(client.list_identity_entities("query { test }"))

        assert len(result) == 2
        assert result[0]["entityId"] == "1"
        assert result[1]["entityId"] == "2"

    def test_list_identity_entities_empty_response(self, client):
        client.request_graphql_endpoint = Mock(return_value=iter([]))

        result = list(client.list_identity_entities("query { test }"))

        assert result == []

    def test_list_identity_entities_handles_none_response(self, client):
        client.request_graphql_endpoint = Mock(return_value=None)

        with pytest.raises(TypeError):
            list(client.list_identity_entities("query { test }"))

    def test_list_identity_entities_passes_correct_parameters(self, client):
        client.request_graphql_endpoint = Mock(return_value=iter([]))

        list(client.list_identity_entities("query { test }"))

        client.request_graphql_endpoint.assert_called_once_with(
            endpoint="/identity-protection/combined/graphql/v1",
            query="query { test }",
            data_path=["entities", "nodes"],
        )
