from functools import cached_property
from typing import Any
from urllib.parse import urljoin

import requests
from sekoia_automation.account_validator import AccountValidator

from harfanglab.client import ApiClient
from harfanglab.helpers import handle_uri


class HarfanglabCredentialsTimeoutError(Exception):
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

    def _check_credentials_request(self) -> tuple[dict[str, Any], int]:
        check_cred_url = urljoin(self.base_url, self.AUTHENTICATION_ENDPOINT)
        params: dict = {}

        try:
            check_cred_response = self.client.get(check_cred_url, params=params, timeout=self.TIMEOUT)
            check_cred_response.raise_for_status()
            return check_cred_response.json(), check_cred_response.status_code
        except requests.Timeout:
            raise HarfanglabCredentialsTimeoutError(
                f"Timeout while checking credentials for Harfanglab asset connector at {check_cred_url}"
            )

    def validate(self) -> bool:
        check_cred_response, status_code = self._check_credentials_request()
        if status_code == 200:
            self.log(
                message="Successfully validated credentials for Harfanglab asset connector",
                level="info",
            )
            return True
        elif status_code == 401:
            self.log(
                message="Invalid credentials for Harfanglab asset connector",
                level="error",
            )
            return False
        else:
            self.log(
                message=f"Unexpected status code {status_code} while validating credentials for Harfanglab asset connector",
                level="error",
            )
            return False
