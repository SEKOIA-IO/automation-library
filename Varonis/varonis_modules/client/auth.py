from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class VaronisApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class VaronisAuthenticationError(Exception):
    def __init__(self, error: str, error_description: str):
        self.error = error
        self.error_description = error_description

    def __str__(self):
        return f"{self.error}: {self.error_description}"


class VaronisApiAuthentication(AuthBase):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        ratelimit_per_second: int = 10,
    ) -> None:
        self.__authorization_url = urljoin(base_url, "api/authentication/api_keys/token")
        self.__api_key = api_key
        self.__api_credentials: VaronisApiCredentials | None = None

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

    def get_credentials(self) -> VaronisApiCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data="grant_type=varonis_custom",
                headers={
                    "x-api-key": self.__api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=60,
            )
            try:
                response.raise_for_status()

            except requests.HTTPError:
                if response.status_code in (401, 403):
                    raw = response.json()
                    raise VaronisAuthenticationError(error=raw["error"], error_description=raw["error_description"])

            api_credentials: dict = response.json()

            credentials = VaronisApiCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
