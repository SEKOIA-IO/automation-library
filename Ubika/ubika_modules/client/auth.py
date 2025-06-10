from datetime import datetime, timedelta

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class AuthorizationError(Exception):
    pass


class ApiKeyAuthentication(AuthBase):
    def __init__(self, token: str):
        self.__token = token

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.__token}"
        return request


class UbikaCloudProtectorNextGenCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class UbikaCloudProtectorNextGenAuthentication(AuthBase):
    def __init__(
        self,
        refresh_token: str,
        ratelimit_per_minute: int = 20,
    ) -> None:
        self.__authorization_url = "https://login.ubika.io/auth/realms/main/protocol/openid-connect/token"
        self.__refresh_token = refresh_token
        self.__api_credentials: UbikaCloudProtectorNextGenCredentials | None = None

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

    def get_credentials(self) -> UbikaCloudProtectorNextGenCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=30) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data={"grant_type": "refresh_token", "client_id": "rest-api", "refresh_token": self.__refresh_token},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=60,
            )
            try:
                response.raise_for_status()

            except requests.exceptions.RequestException as e:
                raw = response.json()
                raise AuthorizationError(raw["error"], raw["error_description"]) from e

            api_credentials: dict = response.json()

            credentials = UbikaCloudProtectorNextGenCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
