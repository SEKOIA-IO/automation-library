from functools import cached_property

import requests.exceptions
from sekoia_automation.account_validator import AccountValidator

from . import ZimperiumModule
from .client import ZimperiumApiAuthentication


class ZimperiumAccountValidator(AccountValidator):
    module: ZimperiumModule

    @cached_property
    def auth(self) -> ZimperiumApiAuthentication:
        return ZimperiumApiAuthentication(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    def validate(self) -> bool:
        try:
            self.auth.get_credentials()
            self.log("Credentials validated", level="info")
            return True

        except requests.HTTPError as http_err:
            self.log(f"HTTP error during credential validation: {http_err}", level="error")
            self.error(f"Failed to validate Zimperium MTD credentials due to HTTP error: {http_err}")
            return False

        except requests.RequestException as req_err:
            self.log(f"Network error during credential validation: {req_err}", level="error")
            self.error(f"Failed to validate Zimperium MTD credentials due to network error: {req_err}")
            return False

        except Exception as exc:
            self.log_exception(exc, message="Unexpected error during credential validation")
            self.error("Failed to validate Zimperium MTD credentials due to an unexpected error")
            return False
