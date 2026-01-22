from tenable_conn import TenableModule
from tenable_conn.account_validator import TenableAccountValidator
from tenable_conn.asset_connector.vulnerability_asset import TenableAssetConnector

if __name__ == "__main__":
    module = TenableModule()
    module.register_account_validator(TenableAccountValidator)
    module.register(TenableAssetConnector, "tenable_vuln_asset_connector")

    module.run()
