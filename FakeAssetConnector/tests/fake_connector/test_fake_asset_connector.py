import pytest
from unittest.mock import Mock

from asset_connector.models import AssetConnectorModule
from asset_connector.fake_connector.fake_asset_connector import FakeAssetConnector


@pytest.fixture
def test_asset_connector(data_storage):
    module = AssetConnectorModule()
    module.configuration = {
        "len_data_to_send": "10",
        "time_sleep": "1",
    }

    test_connector = FakeAssetConnector(module=module, data_path=data_storage)
    test_connector.configuration = {
        "sekoia_base_url": "http://example.com",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60
    }

    test_connector.log = Mock()
    test_connector.log_exception = Mock()

    yield test_connector


def test_generate_fake_api_call(test_asset_connector):
    pass
