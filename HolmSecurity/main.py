from sekoia_automation.module import Module

from holm_security.account_validator import HolmSecurityAccountValidator
from holm_security.asset_connector.device_assets import HolmSecurityDeviceAssetConnector

if __name__ == "__main__":
    module = Module()
    module.register_account_validator(HolmSecurityAccountValidator)
    module.register(HolmSecurityDeviceAssetConnector, "holm_security_device_asset_connector")
    module.run()
