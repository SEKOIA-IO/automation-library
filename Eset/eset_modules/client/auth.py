from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class EsetProtectApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class EsetProtectApiAuthentication(AuthBase):
    def __init__(
        self,
        auth_base_url: str,
        username: str,
        password: str,
        ratelimit_per_second: int = 10,
    ) -> None:
        self.__authorization_url = urljoin(auth_base_url, "oauth/token")
        self.__username = username
        self.__password = password
        self.__api_credentials: EsetProtectApiCredentials | None = None

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

    def get_credentials(self) -> EsetProtectApiCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data={
                    "grant_type": "password",
                    "username": self.__username,
                    "password": self.__password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60,
            )
            response.raise_for_status()

            api_credentials: dict = response.json()

            credentials = EsetProtectApiCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
