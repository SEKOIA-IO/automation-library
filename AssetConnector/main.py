from connectors.fake_asset_connector import FakeAssetConnectorModule, FakeAssetConnector

if __name__ == "__main__":
    module = FakeAssetConnectorModule()
    module.register(FakeAssetConnector, "fake_asset_connector")
    module.run()
