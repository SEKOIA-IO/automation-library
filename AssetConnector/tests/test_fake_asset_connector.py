import pytest
from unittest.mock import Mock

from asset_connector.fake_asset_connector import FakeAssetConnector, FakeAssetConnectorModule


@pytest.fixture
def test_asset_connector(data_storage):
    module = FakeAssetConnectorModule()
    module.configuration = {"len_data_to_send": 10, "time_sleep": 1}

    test_connector = FakeAssetConnector(module=module, data_path=data_storage)
    test_connector.configuration = {
        "sekoia_base_url": "http://example.com",
        "api_key": "fake_api_key",
        "frequency": 60,
    }

    test_connector.log = Mock()
    test_connector.log_exception = Mock()

    yield test_connector


def test_generate_fake_api_call(test_asset_connector):
    api_response = test_asset_connector._generate_fake_api_call()
    assert "data" in api_response
    assert "total" in api_response
    assert api_response["total"] == 10
    assert api_response["data"][0]["name"] is not None
    assert api_response["data"][0]["type"] in ["account", "host"]
    assert all(isinstance(asset, dict) for asset in api_response["data"])
