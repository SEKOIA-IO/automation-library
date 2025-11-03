import requests

from sekoia_automation.account_validator import AccountValidator

from microsoft_ad.client.ldap_client import LDAPClient


class MicrosoftADAccountValidator(AccountValidator, LDAPClient):

    def validate(self) -> bool:
        self.log(message="Start Validation credentials process for Microsoft AD asset connector", level="info")

        try:
            self.ldap_client.bind()
            self.log(
                message="Successfully validated credentials for Microsoft AD asset connector",
                level="info",
            )
            return True
        except requests.HTTPError as http_err:
            self.log(message=f"HTTP error validating Microsoft AD credentials: {http_err}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to HTTP error: {http_err}")
            return False
        except requests.RequestException as req_err:
            self.log(message=f"Network error when contacting Microsoft AD: {req_err}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to network error: {req_err}")
            return False
        except Exception as error:
            self.log_exception(error, message=f"Failed to validate Microsoft AD credentials : {error}")
            self.error(message=f"Failed to validate Microsoft AD credentials due to unknown error: {error}")
            return False