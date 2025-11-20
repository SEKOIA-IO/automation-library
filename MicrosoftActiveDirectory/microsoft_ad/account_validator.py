# Import ldap3 exceptions
from ldap3.core.exceptions import LDAPSocketOpenError, LDAPBindError

# Import sekoia libraries
from sekoia_automation.account_validator import AccountValidator

# Import internal classes, functions, and models
from microsoft_ad.client.ldap_client import LDAPClient


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
        # Handle lDAP Timeout Error
        except LDAPSocketOpenError as ldap_socket_timeout_err:
            self.log(message=f"LDAP socket timeout error : {ldap_socket_timeout_err}", level="error")
            self.error(
                message=f"Failed to validate Microsoft AD credentials due to LDAP timeout error: {ldap_socket_timeout_err}"
            )
            return False
        # Handle LDAP Bind Error
        except LDAPBindError as bind_err:
            self.log(message=f"LDAP bind error : {bind_err}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to LDAP bind error: {bind_err}")
            return False
        # Handle any other exceptions
        except Exception as ldap_error:
            self.log(message=f"Failed to validate Microsoft AD credentials : {ldap_error}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to unknown error: {ldap_error}")
            return False
