import os
import pytest
from unittest.mock import Mock
from collections.abc import Generator

from asset_connector.base import AssetConnector
from asset_connector.models import AssetList, AssetObject


class FakeAssetConnector(AssetConnector):
    assets: AssetList | None = None

    def set_assets(self, assets: AssetList) -> None:
        self.assets = assets

    def get_assets(self) -> Generator[AssetObject, None, None]:
        """
        Fake method to simulate asset retrieval.
        Yields:
            AssetObject: Fake asset object.
        """

        if self.assets is None:
            raise ValueError("Assets not set")

        yield from self.assets.assets


@pytest.fixture
def test_asset_connector():
    test_connector = FakeAssetConnector()

    test_connector.configuration = {
        "sekoia_base_url": "http://example.com",
        "api_key": "fake_api_key",
        "frenquency": 60,
    }

    test_connector.log = Mock()
    test_connector.log_exception = Mock()

    yield test_connector


@pytest.fixture
def asset_list():
    return AssetList(assets=[AssetObject(name="Asset1", type="account"), AssetObject(name="Asset2", type="host")])


@pytest.mark.skipif("{'ASSET_CONNECTOR_BATCH_SIZE'}" ".issubset(os.environ.keys()) == False")
def test_batch_size_env_var_exist(test_asset_connector):
    connector_batch_size = test_asset_connector.batch_size
    assert connector_batch_size == os.environ.get("ASSET_CONNECTOR_BATCH_SIZE")


def test_batch_size_env_var_not_exist(test_asset_connector):
    connector_batch_size = test_asset_connector.batch_size
    assert connector_batch_size == 1000


@pytest.mark.skipif("{'ASSET_CONNECTOR_PRODUCTION_BASE_URL'}" ".issubset(os.environ.keys()) == False")
def test_base_url_env_var_exist(test_asset_connector):
    connector_base_url = test_asset_connector.production_base_url
    assert connector_base_url == os.environ.get("ASSET_CONNECTOR_PRODUCTION_BASE_URL")


def test_base_url_env_var_not_exist(test_asset_connector):
    connector_base_url = test_asset_connector.production_base_url
    assert connector_base_url == "https://api.sekoia.io"


@pytest.mark.skipif("{'ASSET_CONNECTOR_FREQUENCY'}" ".issubset(os.environ.keys()) == False")
def test_frequency_env_var_exist(test_asset_connector):
    connector_frequency = test_asset_connector.frequency
    assert connector_frequency == int(os.environ.get("ASSET_CONNECTOR_FREQUENCY"))


def test_frequency_env_var_not_exist(test_asset_connector):
    connector_frequency = test_asset_connector.frequency
    assert connector_frequency == 60


def test_http_header(test_asset_connector):
    test_asset_connector.connector_configuration_uuid = "04716e25-c97f-4a22-925e-8b636ad9c8a4"
    headers = test_asset_connector.http_header
    assert headers["Authorization"] == "Bearer fake_api_key"
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "sekoiaio-asset-connnector-04716e25-c97f-4a22-925e-8b636ad9c8a4"


def test_handle_api_error(test_asset_connector):
    error_code = 400
    error_message = test_asset_connector.handle_api_error(error_code)
    assert error_message == "Invalid request format"

    error_code = 401
    error_message = test_asset_connector.handle_api_error(error_code)
    assert error_message == "Unauthorized access"

    error_code = 404
    error_message = test_asset_connector.handle_api_error(error_code)
    assert error_message == "Connector not found"

    error_code = 500
    error_message = test_asset_connector.handle_api_error(error_code)
    assert error_message == "An unknown error occurred"


def test_post_assets_to_api_success(test_asset_connector, asset_list):
    test_asset_connector._http_session.post = Mock(
        return_value=Mock(status_code=200, json=lambda: {"result": "success"})
    )
    response = test_asset_connector.post_assets_to_api(asset_list, "http://example.com/api")
    assert response == {"result": "success"}


def test_post_assets_to_api_failure(test_asset_connector, asset_list):
    test_asset_connector._http_session.post = Mock(return_value=Mock(status_code=400))
    response = test_asset_connector.post_assets_to_api(asset_list, "http://example.com/api")
    assert response is None


def test_push_assets_to_sekoia(test_asset_connector):
    test_asset_connector.post_assets_to_api = Mock(return_value={"result": "success"})
    test_asset_connector.connector_configuration_uuid = "04716e25-c97f-4a22-925e-8b636ad9c8a4"
    assets = [{"type": "account", "name": "Asset1"}, {"type": "host", "name": "Asset2"}]
    test_asset_connector.push_assets_to_sekoia(assets)
    test_asset_connector.post_assets_to_api.assert_called_once()
    call_args = test_asset_connector.post_assets_to_api.call_args
    pos_args, kw_args = call_args
    assert kw_args["assets"] == assets
    assert (
        kw_args["asset_connector_api_url"]
        == "http://example.com/api/v1/asset-connectors/04716e25-c97f-4a22-925e-8b636ad9c8a4"
    )


def test_asset_fetch_cycle(test_asset_connector):
    test_asset_connector.get_assets = Mock(
        return_value=iter([{"type": "account", "name": "Asset1"}, {"type": "host", "name": "Asset2"}])
    )
    test_asset_connector.push_assets_to_sekoia = Mock()
    test_asset_connector.asset_fetch_cycle()
    test_asset_connector.push_assets_to_sekoia.assert_called_once()

    assert test_asset_connector.push_assets_to_sekoia.call_count == 1
    assert test_asset_connector.push_assets_to_sekoia.call_args[0][0] == [
        {"type": "account", "name": "Asset1"},
        {"type": "host", "name": "Asset2"},
    ]
