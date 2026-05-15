import requests
from functools import cached_property

from sekoia_automation.account_validator import AccountValidator

from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosApiAuthenticationError


class SophosAccountValidator(AccountValidator):
    """
    Validates Sophos credentials by attempting to obtain an OAuth2 token
    and calling the /whoami/v1 endpoint to verify tenancy access.
    """

    def _build_auth(self) -> SophosApiAuthentication:
        cfg = self.module.configuration
        return SophosApiAuthentication(
            api_host=cfg.api_host,
            authorization_url=cfg.oauth2_authorization_url,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
        )

    @cached_property
    def auth_client(self) -> SophosApiAuthentication:
        return self._build_auth()

    def validate(self) -> bool:
        self.log("Starting credential validation for Sophos", level="info")

        try:
            credentials = self.auth_client.get_credentials()

            if not credentials or not credentials.access_token:
                self.log("Failed to obtain access token from Sophos", level="error")
                self.error("Failed to validate Sophos credentials: no access token returned")
                return False

            self.log(
                f"Credentials validated – tenancy_type={credentials.tenancy_type}, "
                f"tenancy_id={credentials.tenancy_id}",
                level="info",
            )
            return True

        except SophosApiAuthenticationError as auth_err:
            self.log(f"Authentication error: {auth_err}", level="error")
            self.error(f"Failed to validate Sophos credentials: {auth_err}")
            return False

        except requests.HTTPError as http_err:
            self.log(f"HTTP error during credential validation: {http_err}", level="error")
            self.error(f"Failed to validate Sophos credentials due to HTTP error: {http_err}")
            return False

        except requests.RequestException as req_err:
            self.log(f"Network error during credential validation: {req_err}", level="error")
            self.error(f"Failed to validate Sophos credentials due to network error: {req_err}")
            return False

        except Exception as exc:
            self.log_exception(exc, message="Unexpected error during credential validation")
            self.error("Failed to validate Sophos credentials due to an unexpected error")
            return False
