from easyvista_modules import EasyVistaModule
from easyvista_modules.account_validator import EasyVistaAccountValidator
from easyvista_modules.asset_connector.device_assets import EasyVistaDeviceAssetConnector


def main():
    module = EasyVistaModule()
    module.register_account_validator(EasyVistaAccountValidator)
    module.register(EasyVistaDeviceAssetConnector, "easyvista_device_asset_connector")
    module.run()


if __name__ == "__main__":
    main()
