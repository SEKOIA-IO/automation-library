from typing import Any
from urllib.parse import urljoin

import msal
from requests.auth import AuthBase


class AuthenticationError(Exception):
    def __init__(self, message: str, result: dict[str, Any] | None = None):
        self.message = message
        self.result = result

    def __str__(self) -> str:
        return self.message


class ApiKeyAuthentication(AuthBase):
    def __init__(self, base_url: str, tenant_id: str, client_id: str, client_secret: str, scopes: list[str]) -> None:
        self.__base_url = base_url
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__tenant_id = tenant_id
        self.__scopes = scopes

        authority = urljoin(self.__base_url, self.__tenant_id.lstrip("/"))
        self.app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret,
        )

    @property
    def access_token(self) -> str:
        # all token requests by MSAL package are cached and refreshed when needed
        result_token_silent: dict | None = self.app.acquire_token_silent(scopes=self.__scopes, account=None)

        if result_token_silent:
            return result_token_silent["access_token"]

        result: dict = self.app.acquire_token_for_client(scopes=self.__scopes)
        if "access_token" in result:
            return result["access_token"]

        raise AuthenticationError(
            "Authentication failed. Please check your client ID, client secret and tenant ID.", result=result
        )

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        return request
