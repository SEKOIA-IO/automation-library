from FakeAssetConnector.fake_asset_connector.fake_connector import FakeAssetConnector
from FakeAssetConnector.fake_asset_connector.models import FakeAssetModule
from FakeAssetConnector.fake_asset_connector.account_validator import FakeAssetAccountValidator

if __name__ == "__main__":
    module = FakeAssetModule()
    module.register_account_validator(FakeAssetAccountValidator)
    module.register(FakeAssetConnector, "fake_asset_connector")
    module.run()
