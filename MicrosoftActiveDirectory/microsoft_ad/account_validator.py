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

        self.log(
            message="[validate] Start Validation credentials process for Microsoft AD asset connector",
            level="info",
        )
        self.log(
            message=f"[validate] ldap_client.bound before check: {self.ldap_client.bound}",
            level="debug",
        )

        try:
            # Only bind if not already bound
            if not self.ldap_client.bound:
                self.log(
                    message="[validate] Connection not bound yet — calling bind()",
                    level="debug",
                )
                self.ldap_client.bind()
                self.log(
                    message=f"[validate] bind() result: {self.ldap_client.result}",
                    level="debug",
                )
            else:
                self.log(
                    message="[validate] Connection already bound, skipping bind()",
                    level="debug",
                )

            self.log(
                message=f"[validate] Connection bound={self.ldap_client.bound} tls_started={self.ldap_client.tls_started}",
                level="debug",
            )
            self.log(
                message="[validate] Successfully validated credentials for Microsoft AD asset connector",
                level="info",
            )
            return True
        # Handle lDAP Timeout Error
        except LDAPSocketOpenError as ldap_socket_timeout_err:
            self.log(
                message=f"[validate] LDAPSocketOpenError: {ldap_socket_timeout_err}",
                level="error",
            )
            self.error(
                message=f"Failed to validate Microsoft AD credentials due to LDAP timeout error: {ldap_socket_timeout_err}"
            )
            return False
        # Handle LDAP Bind Error
        except LDAPBindError as bind_err:
            self.log(message=f"[validate] LDAPBindError: {bind_err}", level="error")
            self.error(message=f"Failed to validate Microsoft AD credentials due to LDAP bind error: {bind_err}")
            return False
        # Handle any other exceptions
        except Exception as ldap_error:
            self.log(
                message=f"[validate] Unexpected error ({type(ldap_error).__name__}): {ldap_error}",
                level="error",
            )
            self.error(message=f"Failed to validate Microsoft AD credentials due to unknown error: {ldap_error}")
            return False
