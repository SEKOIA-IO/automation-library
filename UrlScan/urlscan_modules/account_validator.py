from sekoia_automation.account_validator import AccountValidator

from urlscan_modules import UrlScanModule
from urlscan_modules.base import describe_error, new_client


class UrlScanAccountValidator(AccountValidator):
    module: UrlScanModule

    def validate(self) -> bool:
        try:
            with new_client(self.module.configuration) as client:
                client.get_quotas()
            return True
        except Exception as error:
            message = describe_error(error)

        self.log(message, level="error")
        # Without self.error() the platform has no message to display and shows "Unknown error"
        self.error(message)
        return False
