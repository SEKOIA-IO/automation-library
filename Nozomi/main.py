from nozomi_networks import NozomiModule
from nozomi_networks.account_validator import NozomiAccountValidator
from nozomi_networks.asset_connector.device_assets import NozomiDeviceAssetConnector
from nozomi_networks.nozomi_vantage_connector import NozomiVantageConnector

if __name__ == "__main__":
    module = NozomiModule()

    module.register_account_validator(NozomiAccountValidator)
    module.register(NozomiVantageConnector, "nozomi_vantage")
    module.register(NozomiDeviceAssetConnector, "nozomi_device_asset_connector")

    module.run()
