from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class ZimperiumApiCredentials:
    token_type: str = "Bearer"
    refresh_token: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class ZimperiumApiAuthentication(AuthBase):
    AUTH_TTL = 60 * 60

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        ratelimit_per_second: int = 10,
    ) -> None:
        self.__base_url = base_url
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__api_credentials: ZimperiumApiCredentials | None = None

        self.__http_session = requests.Session()
        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                ),
            ),
        )

    def get_credentials(self) -> ZimperiumApiCredentials:
        current_dt = datetime.now(timezone.utc)

        refresh_token = (
            self.__api_credentials.refresh_token if self.__api_credentials else None
        )
        if (
            self.__api_credentials is None
            or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at
        ):
            if refresh_token:
                response = self.__http_session.post(
                    url=urljoin(self.__base_url, "/api/auth/v1/api_keys/access"),
                    json={"refreshToken": refresh_token},
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )

            else:
                response = self.__http_session.post(
                    url=urljoin(self.__base_url, "api/auth/v1/api_keys/login"),
                    json={"clientId": self.__client_id, "secret": self.__client_secret},
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )

            response.raise_for_status()

            api_credentials: dict[str, Any] = response.json()
            credentials = ZimperiumApiCredentials()
            credentials.access_token = api_credentials["accessToken"]
            credentials.refresh_token = api_credentials["refreshToken"]
            credentials.expires_at = current_dt + timedelta(seconds=self.AUTH_TTL)
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
