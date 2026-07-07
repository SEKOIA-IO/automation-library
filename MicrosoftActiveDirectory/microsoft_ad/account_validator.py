from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
from microsoft_ad.client.ldap_client import LDAPClient

from sekoia_automation.account_validator import AccountValidator



class MicrosoftADAccountValidator(AccountValidator, LDAPClient):
    """Account validator for Microsoft AD asset connector."""

    def validate(self) -> bool:
        """
        Validate the credentials for Microsoft AD asset connector.
        :return:
        bool: True if the credentials are valid, False otherwise.
        """

        self.log(message="Start Validation credentials process for Microsoft AD asset connector", level="info")

        try:
            # Only bind if not already bound
            if not self.ldap_client.bound:
                self.ldap_client.bind()
            self.log(
                message="Successfully validated credentials for Microsoft AD asset connector",
                level="info",
            )
            return True
        except LDAPSocketOpenError as ldap_socket_timeout_err:
            self.log(message=f"LDAP socket timeout error : {ldap_socket_timeout_err}", level="error")
            self.error(
                message=f"Failed to validate Microsoft AD credentials due to LDAP timeout error: {ldap_socket_timeout_err}"
            )
            return False
        except LDAPBindError as bind_err:
            self.log(message=f"LDAP bind error : {bind_err}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to LDAP bind error: {bind_err}")
            return False
        except Exception as ldap_error:
            self.log(message=f"Failed to validate Microsoft AD credentials : {ldap_error}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to unknown error: {ldap_error}")
            return False
