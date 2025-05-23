from datetime import datetime, timedelta

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class LookoutApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class LookoutApiAuthentication(AuthBase):
    def __init__(
        self,
        base_url: str,
        api_token: str,
        ratelimit_per_minute: int = 10,
    ) -> None:
        self.__authorization_url = f"{base_url}/oauth2/token"
        self.__token = api_token
        self.__api_credentials: LookoutApiCredentials | None = None

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

    def get_credentials(self) -> LookoutApiCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data="grant_type=client_credentials",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Bearer {self.__token}",
                },
                timeout=60,
            )
            response.raise_for_status()

            api_credentials: dict = response.json()

            credentials = LookoutApiCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
