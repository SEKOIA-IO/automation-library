from functools import cached_property
from typing import Any
from urllib.parse import urljoin

from requests.exceptions import RequestException, Timeout
from sekoia_automation.account_validator import AccountValidator

from harfanglab.client import ApiClient
from harfanglab.helpers import handle_uri


class HarfanglabCredentialsError(Exception):
    """Base exception for credential validation errors."""

    pass


class HarfanglabCredentialsTimeoutError(HarfanglabCredentialsError):
    pass


class HarfanglabCredentialsConnectionError(HarfanglabCredentialsError):
    pass


class HarfanglabCredentialsUnexpectedError(HarfanglabCredentialsError):
    pass


class HarfanglabAccountValidator(AccountValidator):

    TIMEOUT = 30
    AUTHENTICATION_ENDPOINT = "/api/auth/users/me"

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(token=self.module.configuration["api_token"], instance_url=self.base_url)

    @cached_property
    def base_url(self) -> str:
        return handle_uri(self.module.configuration["url"])

    @cached_property
    def auth_url(self) -> str:
        return urljoin(self.base_url, self.AUTHENTICATION_ENDPOINT)

    def _check_credentials_request(self) -> tuple[dict[str, Any], int]:

        try:
            check_cred_response = self.client.get(self.auth_url, timeout=self.TIMEOUT)
            return check_cred_response.json(), check_cred_response.status_code
        except Timeout:
            raise HarfanglabCredentialsTimeoutError(
                f"Timeout while checking credentials for Harfanglab at {self.auth_url}"
            )
        except RequestException as e:
            raise HarfanglabCredentialsConnectionError(
                f"Network error while trying to reach {self.auth_url}. Reason: {e}"
            )
        except Exception as e:
            raise HarfanglabCredentialsUnexpectedError(
                f"An unexpected error occurred while checking credentials : {e}"
            ) from e

    def validate(self) -> bool:
        self.log(message="Start Validation credentials process for Harfanglab asset connector", level="info")

        try:
            check_cred_response, status_code = self._check_credentials_request()

            if 400 <= status_code < 500:
                self.log(
                    message=f"{status_code} Client Error: {check_cred_response.get('detail', 'No details')} for base url: {self.base_url}",
                    level="error",
                )
                self.error(message=f"Failed to validate Harfanglab credentials : {check_cred_response.get('detail', 'No details')}")
                return False

            elif 500 <= status_code < 600:
                self.log(
                    message=f"{status_code} Server Error: {check_cred_response.get('detail', 'No details')} for base url: {self.base_url}",
                    level="error",
                )
                self.error(message=f"Failed to validate Harfanglab credentials : {check_cred_response.get('detail', 'No details')}")
                return False

            self.log(message="Credentials validated successfully", level="info")
            return True

        except HarfanglabCredentialsError as e:
            self.log(message=str(e), level="error")
            self.error(message=f"Failed to validate Harfanglab credentials : {e}")
            return False
