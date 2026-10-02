from google.auth.transport.requests import Request
from google.oauth2 import service_account
from sekoia_automation.account_validator import AccountValidator

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class GoogleAccountValidator(AccountValidator):
    """
    Check the service account key by exchanging it for an access token.

    Domain-wide delegation and the administrator mail belong to connector configurations: they are not checked.
    """

    def validate(self) -> bool:
        """Return True when Google issues an access token for the service account key."""
        try:
            credentials = service_account.Credentials.from_service_account_info(
                self.module.configuration["credentials"], scopes=[CLOUD_PLATFORM_SCOPE]
            )
            credentials.refresh(Request())
        except Exception as error:
            message = f"Invalid Google service account credentials: {error}"
            self.log(message, level="error")
            self.error(message)
            return False
        return True
