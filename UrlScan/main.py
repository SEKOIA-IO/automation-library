from urlscan_modules import UrlScanModule
from urlscan_modules.account_validator import UrlScanAccountValidator

if __name__ == "__main__":
    module = UrlScanModule()
    module.register_account_validator(UrlScanAccountValidator)
    module.run()
