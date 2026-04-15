from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import msal
import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from .retry import Retry


class AuthenticationError(Exception):
    def __init__(self, message: str, result: dict[str, Any] | None = None):
        self.message = message
        self.result = result

    def __str__(self) -> str:
        return self.message


class MicrosoftDefenderCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class ApiKeyAuthentication(AuthBase):
    def __init__(self, app_id: str, app_secret: str, tenant_id: str, ratelimit_per_minute: int):
        self.__app_id = app_id
        self.__app_secret = app_secret
        self.__tenant_id = tenant_id

        self.__api_credentials: MicrosoftDefenderCredentials | None = None

        self.__http_session = requests.Session()
        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                per_minute=ratelimit_per_minute,
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                ),
            ),
        )

    def get_credentials(self) -> MicrosoftDefenderCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            url = "https://login.microsoftonline.com/%s/oauth2/token" % self.__tenant_id
            resource_app_id_uri = "https://api.securitycenter.microsoft.com"
            body = {
                "resource": resource_app_id_uri,
                "client_id": self.__app_id,
                "client_secret": self.__app_secret,
                "grant_type": "client_credentials",
            }

            response = self.__http_session.get(url, data=body)
            response.raise_for_status()

            credentials = MicrosoftDefenderCredentials()

            api_credentials: dict = response.json()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=int(api_credentials["expires_in"]))
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request


class GraphApiKeyAuthentication(AuthBase):
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
