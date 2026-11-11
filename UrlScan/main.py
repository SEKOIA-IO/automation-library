from urlscan_modules import UrlScanModule
from urlscan_modules.account_validator import UrlScanAccountValidator
from urlscan_modules.get_scan_result import GetScanResult

if __name__ == "__main__":
    module = UrlScanModule()
    module.register_account_validator(UrlScanAccountValidator)
    module.register(GetScanResult, "urlscan_get_scan_result")
    module.run()
