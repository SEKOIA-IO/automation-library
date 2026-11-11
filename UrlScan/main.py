from urlscan_modules import UrlScanModule
from urlscan_modules.account_validator import UrlScanAccountValidator
from urlscan_modules.download_scan_screenshot import DownloadScanScreenshot
from urlscan_modules.get_scan_result import GetScanResult
from urlscan_modules.scan_url import ScanUrl
from urlscan_modules.search import Search

if __name__ == "__main__":
    module = UrlScanModule()
    module.register_account_validator(UrlScanAccountValidator)
    module.register(ScanUrl, "urlscan_scan_url")
    module.register(GetScanResult, "urlscan_get_scan_result")
    module.register(DownloadScanScreenshot, "urlscan_download_scan_screenshot")
    module.register(Search, "urlscan_search")
    module.run()
