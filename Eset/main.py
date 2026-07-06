from eset_modules import EsetModule
from eset_modules.account_validator import EsetAccountValidator
from eset_modules.action_deisolate_endpoint import EsetDeIsolateEndpointAction
from eset_modules.action_isolate_endpoint import EsetIsolateEndpointAction
from eset_modules.action_scan import EsetScanAction
from eset_modules.asset_connector.device_assets import EsetDeviceAssetConnector
from eset_modules.asset_connector.user_assets import EsetUserAssetConnector
from eset_modules.asset_connector.vulnerability_assets import EsetVulnerabilityAssetConnector

if __name__ == "__main__":
    module = EsetModule()
    module.register(EsetScanAction, "EsetScanAction")
    module.register(EsetIsolateEndpointAction, "EsetIsolateEndpointAction")
    module.register(EsetDeIsolateEndpointAction, "EsetDeIsolateEndpointAction")
    module.register(EsetDeviceAssetConnector, "eset_device_asset_connector")
    module.register(EsetVulnerabilityAssetConnector, "eset_vuln_asset_connector")
    module.register(EsetUserAssetConnector, "eset_user_asset_connector")
    module.register_account_validator(EsetAccountValidator)
    module.run()
