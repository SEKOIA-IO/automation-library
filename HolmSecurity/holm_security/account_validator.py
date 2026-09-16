from functools import cached_property

from requests import Response
from requests.exceptions import RequestException, Timeout
from sekoia_automation.account_validator import AccountValidator

from holm_security.client import ApiClient


class HolmSecurityAccountValidator(AccountValidator):
    """Validate Holm Security credentials against the endpoints used by the connectors.

    The token is confirmed valid only when every endpoint used by the connectors
    returns ``200 OK``: the two inventories and the vulnerability report.
    """

    TIMEOUT = 30
    # (endpoint, query parameters) pairs that must each return 200. The Holm API
    # paginates with `limit`/`offset`; `page_size` is silently ignored.
    VALIDATION_ENDPOINTS: list[tuple[str, dict[str, int]]] = [
        ("/v2/devices", {"limit": 1}),
        ("/v2/net-assets", {"limit": 1}),
        # Authorization probe: without the `assets` filter this endpoint answers 200
        # with an empty page, so it proves the token may read the vulnerability
        # report without depending on the tenant holding any network asset.
        ("/v2/net-assets/report/vulnerabilities/", {"limit": 1}),
    ]

    @cached_property
    def base_url(self) -> str:
        return str(self.module.configuration["base_url"]).rstrip("/")

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(base_url=self.base_url, token=self.module.configuration["api_token"])

    @staticmethod
    def _describe_error(url: str, response: Response) -> str:
        code = response.status_code

        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        if 400 <= code < 500:
            return f"Client error ({code}) while validating Holm Security credentials at {url}: {detail}"

        if 500 <= code < 600:
            return f"Server error ({code}) while validating Holm Security credentials at {url}: {detail}"
        return f"Unexpected status ({code}) while validating Holm Security credentials at {url}: {detail}"

    def _check_endpoint(self, endpoint: str, params: dict[str, int]) -> bool:
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.client.get(url, params=params, timeout=self.TIMEOUT)
        except Timeout:
            message = f"Timeout while validating Holm Security credentials at {url}"
            self.log(message=message, level="error")
            self.error(message)
            return False
        except RequestException as error:
            message = f"Network error while validating Holm Security credentials at {url}: {error}"
            self.log(message=message, level="error")
            self.error(message)
            return False
        except Exception as error:
            message = f"Unexpected error while validating Holm Security credentials at {url}: {error}"
            self.log(message=message, level="error")
            self.error(message)
            return False

        if response.status_code == 200:
            return True

        message = self._describe_error(url, response)
        self.log(message=message, level="error")
        self.error(message)
        return False

    def validate(self) -> bool:
        self.log(message="Starting credentials validation for Holm Security asset connector", level="info")

        for endpoint, params in self.VALIDATION_ENDPOINTS:
            if not self._check_endpoint(endpoint, params):
                return False

        self.log(message="Holm Security credentials validated successfully", level="info")
        return True
