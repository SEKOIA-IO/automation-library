from sekoia_automation.module import Module

from easyvista.account_validator import EasyVistaAccountValidator
from easyvista.asset_connector.device_assets import EasyVistaDeviceAssetConnector

if __name__ == "__main__":
    module = Module()
    module.register_account_validator(EasyVistaAccountValidator)
    module.register(EasyVistaDeviceAssetConnector, "easyvista_device_asset_connector")
    module.run()
