from urlscan_modules import UrlScanModule
from urlscan_modules.account_validator import UrlScanAccountValidator
from urlscan_modules.get_scan_result import GetScanResult
from urlscan_modules.scan_url import ScanUrl

if __name__ == "__main__":
    module = UrlScanModule()
    module.register_account_validator(UrlScanAccountValidator)
    module.register(ScanUrl, "urlscan_scan_url")
    module.register(GetScanResult, "urlscan_get_scan_result")
    module.run()
