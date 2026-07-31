from functools import cached_property

from requests import Response
from requests.exceptions import RequestException, Timeout
from sekoia_automation.account_validator import AccountValidator

from holm_security.client import ApiClient


class HolmSecurityAccountValidator(AccountValidator):
    """Validate Holm Security credentials by pinging the devices endpoint.

    A ``200 OK`` on ``GET /v2/devices?page_size=1`` confirms the token is valid.
    """

    TIMEOUT = 30
    VALIDATION_ENDPOINT = "/v2/devices"

    @cached_property
    def base_url(self) -> str:
        return str(self.module.configuration["base_url"]).rstrip("/")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(base_url=self.base_url, token=self.module.configuration["api_token"])

    @cached_property
    def validation_url(self) -> str:
        return f"{self.base_url}{self.VALIDATION_ENDPOINT}"

    @staticmethod
    def _describe_error(response: Response) -> str:
        code = response.status_code

        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        if 400 <= code < 500:
            return f"Client error ({code}) while validating Holm Security credentials: {detail}"

        if 500 <= code < 600:
            return f"Server error ({code}) while validating Holm Security credentials: {detail}"
        return f"Unexpected status ({code}) while validating Holm Security credentials: {detail}"

    def validate(self) -> bool:
        self.log(message="Starting credentials validation for Holm Security asset connector", level="info")

        try:
            response = self.client.get(self.validation_url, params={"page_size": 1}, timeout=self.TIMEOUT)
        except Timeout:
            message = f"Timeout while validating Holm Security credentials at {self.validation_url}"
            self.log(message=message, level="error")
            self.error(message)

            return False

        except RequestException as error:
            message = f"Network error while validating Holm Security credentials: {error}"
            self.log(message=message, level="error")
            self.error(message)

            return False

        except Exception as error:
            message = f"Unexpected error while validating Holm Security credentials: {error}"
            self.log(message=message, level="error")
            self.error(message)

            return False

        if response.status_code == 200:
            self.log(message="Holm Security credentials validated successfully", level="info")
            return True

        message = self._describe_error(response)

        self.log(message=message, level="error")
        self.error(message)

        return False
