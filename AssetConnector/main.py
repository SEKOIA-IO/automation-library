from asset_connector.models import AssetConnectorModule
from asset_connector.fake_connector.fake_asset_connector import FakeAssetConnector
from asset_connector.harfanglab_connector.harfanglab_asset_connector import HarfanglabAssetConnector

if __name__ == "__main__":
    module = AssetConnectorModule()
    module.register(FakeAssetConnector, "fake_asset_connector")
    module.register(HarfanglabAssetConnector, "harfanglab_asset_connector")
    module.run()
