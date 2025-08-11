import pytest
from unittest.mock import Mock
import datetime

import requests_mock
from sekoia_automation.module import Module
from azure_ad.asset_connector.user_assets import EntraIDAssetConnector


@pytest.fixture
def test_entra_id_asset_connector(symphony_storage):
    module = Module()
    module_configuration: dict = {
        "tenant_id": "fake_tenant_id",
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
    }
    module.configuration = module_configuration

    test_entra_id_asset_connector = EntraIDAssetConnector(module=module, data_path=symphony_storage)
    test_entra_id_asset_connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    test_entra_id_asset_connector.log = Mock()
    test_entra_id_asset_connector.log_exception = Mock()

    yield test_entra_id_asset_connector

def test_configuration(test_entra_id_asset_connector):
    assert test_entra_id_asset_connector.module.configuration["tenant_id"] == "fake_tenant_id"
    assert test_entra_id_asset_connector.module.configuration["client_id"] == "fake_client_id"
    assert test_entra_id_asset_connector.module.configuration["client_secret"] == "fake_client_secret"

def test_map_fields(test_entra_id_asset_connector):
    # Mocking the UserOCSFModel and UserOCSF for testing
    from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup
    from msgraph.generated.models.user import User

    # Mocking the user and groups
    asset_user = User(
        user_principal_name="testuser@example.com",
        id="user_id",
        display_name="Test User",
        mail="testuser@example.com"
    )
    has_mfa = True
    asset_groups = []
    result = test_entra_id_asset_connector.map_fields(asset_user, has_mfa, asset_groups)
    assert result.user.name == "testuser@example.com"
    assert result.user.uid == 0
    # assert result.user.groups[0]["name"] == asset_groups[0]["name"]
    assert result.user.has_mfa == has_mfa