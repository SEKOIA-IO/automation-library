import base64
from datetime import datetime, timedelta
from posixpath import join as urljoin

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class ApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class ApiKeyAuthentication(AuthBase):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        access_id: str,
        access_secret: str,
        audience: str | None = None,
        nb_retries: int = 5,
        ratelimit_per_second: int = 20,
    ):
        self.__base_url = base_url
        self.__audience = audience

        # Used in requests as is
        self.__api_key = api_key

        # Used to get auth token
        self.__access_id = access_id
        self.__access_secret = access_secret

        self.__api_credentials: ApiCredentials | None = None
        self.__http_session = requests.Session()
        self.__authorization_url = urljoin(self.__base_url, "oauth/token")

        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

    def __get_authorization_headers(self) -> dict[str, str]:
        digest = base64.b64encode(f"{self.__access_id}:{self.__access_secret}".encode()).decode("utf-8")

        return {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {digest}",
        }

    def __get_authorization_payload(self) -> dict[str, str]:
        data = {"grant_type": "client_credentials", "scope": "api-access"}

        if self.__audience:
            data["audience"] = self.__audience

        return data

    def get_credentials(self) -> ApiCredentials:
        """
        Return CrowdStrike Credentials for the API
        """
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                headers=self.__get_authorization_headers(),
                data=self.__get_authorization_payload(),
            )

            response.raise_for_status()

            credentials = ApiCredentials()

            api_credentials: dict = response.json()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])

            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        request.headers["WatchGuard-API-Key"] = self.__api_key
        return request
