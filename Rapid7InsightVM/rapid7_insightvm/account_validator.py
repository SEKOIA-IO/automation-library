from functools import cached_property
from typing import Any

from requests import Response
from requests.exceptions import ConnectionError, RequestException, Timeout
from sekoia_automation.account_validator import AccountValidator

from rapid7_insightvm.client import ApiClient


class Rapid7InsightVMAccountValidator(AccountValidator):
    """Validate the Insight Platform API key, its region and its access to InsightVM.

    Every endpoint used by the connectors is probed with a one-item page.
    """

    # (HTTP method, endpoint, JSON body) probes that must each return 200.
    VALIDATION_ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
        ("POST", "/assets", {}),
        ("POST", "/vulnerabilities", {}),
    ]
    PROBE_PARAMS: dict[str, int] = {"size": 1}

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient.from_configuration(self.module.configuration)

    def _describe_error(self, url: str, response: Response) -> str:
        code = response.status_code
        try:
            body = response.json()
            detail = body.get("message", body) if isinstance(body, dict) else body
        except ValueError:
            detail = response.text

        if code == 401:
            return (
                f"Invalid API key, or API key from another region: check `api_key` and `region` "
                f"({self.client.region}) (401 at {url}): {detail}"
            )
        if code in (403, 404):
            return (
                "The API key is valid but has no access to InsightVM: use an Organization key or a User key "
                f"with an InsightVM role ({code} at {url}): {detail}"
            )
        if 400 <= code < 500:
            return f"Client error ({code}) while validating the Rapid7 InsightVM API key at {url}: {detail}"
        if 500 <= code < 600:
            return f"Server error ({code}) while validating the Rapid7 InsightVM API key at {url}: {detail}"
        return f"Unexpected status ({code}) while validating the Rapid7 InsightVM API key at {url}: {detail}"

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
        except Timeout:
            return self._fail(f"Timeout while validating the Rapid7 InsightVM API key at {url}")
        except ConnectionError as error:
            return self._fail(
                f"Unable to reach the Insight Platform at {url}: check the region ({self.client.region}): {error}"
            )
        except RequestException as error:
            return self._fail(f"Network error while validating the Rapid7 InsightVM API key at {url}: {error}")
        except Exception as error:
            return self._fail(f"Unexpected error while validating the Rapid7 InsightVM API key at {url}: {error}")

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
