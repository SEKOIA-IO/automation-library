import pytest
from unittest.mock import Mock

from connectors.fake_asset_connector import FakeAssetConnector


@pytest.fixture
def test_asset_connector():
    test_connector = FakeAssetConnector()

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
    assert api_response["total"] == 100
    assert api_response["data"][0]["name"] is not None
    assert api_response["data"][0]["type"] in ["account", "host"]
    assert all(isinstance(asset, dict) for asset in api_response["data"])
