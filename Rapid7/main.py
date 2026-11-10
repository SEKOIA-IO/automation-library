from sekoia_automation.module import Module

from rapid7_insightvm.account_validator import Rapid7InsightVMAccountValidator
from rapid7_insightvm.asset_connector.vulnerability_assets import Rapid7InsightVMVulnerabilityAssetConnector

if __name__ == "__main__":
    module = Module()
    module.register_account_validator(Rapid7InsightVMAccountValidator)
    module.register(Rapid7InsightVMVulnerabilityAssetConnector, "rapid7_insightvm_vulnerability_asset_connector")
    module.run()
