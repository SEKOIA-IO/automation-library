from functools import cached_property
from typing import Any

from requests import Response
from requests.exceptions import ConnectionError, RequestException, SSLError, Timeout
from sekoia_automation.account_validator import AccountValidator

from rapid7_insightvm.client import ApiClient


class Rapid7InsightVMAccountValidator(AccountValidator):
    """Validate the InsightVM credentials against every endpoint used by the connectors.

    InsightVM answers 404 (not 403) to an authenticated account lacking the permission
    to view a collection, so a 404 is reported as a missing permission.
    """

    # (HTTP method, endpoint, JSON body) probes that must each return 200, with one item per page.
    VALIDATION_ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
        ("GET", "/api/3/assets", None),
        ("GET", "/api/3/vulnerabilities", None),
        (
            "POST",
            "/api/3/assets/search",
            {"match": "all", "filters": [{"field": "last-scan-date", "operator": "is-within-the-last", "value": 1}]},
        ),
    ]
    PROBE_PARAMS: dict[str, int] = {"page": 0, "size": 1}

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient.from_configuration(self.module.configuration)

    @staticmethod
    def _describe_error(url: str, response: Response) -> str:
        code = response.status_code
        try:
            body = response.json()
            detail = body.get("message", body) if isinstance(body, dict) else body
        except ValueError:
            detail = response.text

        if code == 401:
            return f"Invalid InsightVM credentials (401) at {url}: check the username and the password: {detail}"
        if code == 404:
            return (
                f"The InsightVM account is authenticated but not allowed to read {url} (404): grant it the "
                f"'View Site Asset Data' or 'View Group Asset Data' permission on the sites in scope: {detail}"
            )
        if 400 <= code < 500:
            return f"Client error ({code}) while validating InsightVM credentials at {url}: {detail}"
        if 500 <= code < 600:
            return f"Server error ({code}) while validating InsightVM credentials at {url}: {detail}"
        return f"Unexpected status ({code}) while validating InsightVM credentials at {url}: {detail}"

    def _fail(self, message: str) -> bool:
        self.log(message=message, level="error")
        self.error(message)
        return False

    def _check_endpoint(self, method: str, endpoint: str, body: dict[str, Any] | None) -> bool:
        url = self.client.url(endpoint)

        try:
            response = self.client.request(
                method, url, params=self.PROBE_PARAMS, json=body, timeout=self.client.TIMEOUT
            )
        except SSLError as error:
            return self._fail(
                f"TLS error while connecting to {url}: {error}. If the Security Console uses a self-signed "
                "certificate, disable 'verify_certificate' in the module configuration"
            )
        except Timeout:
            return self._fail(f"Timeout while validating InsightVM credentials at {url}")
        except ConnectionError as error:
            return self._fail(
                f"Unable to reach the Security Console at {url}: check the host and the port (3780 by default): "
                f"{error}"
            )
        except RequestException as error:
            return self._fail(f"Network error while validating InsightVM credentials at {url}: {error}")
        except Exception as error:
            return self._fail(f"Unexpected error while validating InsightVM credentials at {url}: {error}")

        if response.status_code == 200:
            return True
        return self._fail(self._describe_error(url, response))

    def validate(self) -> bool:
        self.log(message="Starting credentials validation for Rapid7 InsightVM", level="info")

        for method, endpoint, body in self.VALIDATION_ENDPOINTS:
            if not self._check_endpoint(method, endpoint, body):
                return False

        self.log(message="Rapid7 InsightVM credentials validated successfully", level="info")
        return True
