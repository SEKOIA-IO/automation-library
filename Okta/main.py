from okta_modules import OktaModule
from okta_modules.account_validator import OktaAccountValidator
from okta_modules.asset_connector.device_assets import OktaDeviceAssetConnector
from okta_modules.asset_connector.user_assets import OktaUserAssetConnector
from okta_modules.system_log_trigger import SystemLogConnector

if __name__ == "__main__":
    module = OktaModule()
    module.register_account_validator(OktaAccountValidator)
    module.register(OktaDeviceAssetConnector, "device_okta_asset_connector")
    module.register(OktaUserAssetConnector, "user_okta_asset_connector")
    module.register(SystemLogConnector, "okta_system_logs")
    module.run()
