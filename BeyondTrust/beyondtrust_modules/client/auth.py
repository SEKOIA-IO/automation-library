from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase, HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class BeyondTrustApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class BeyondTrustApiAuthentication(AuthBase):
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        ratelimit_per_second: int = 10,
    ) -> None:
        self.__authorization_url = urljoin(base_url, "oauth2/token")
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__api_credentials: BeyondTrustApiCredentials | None = None

        self.__http_session = requests.Session()
        self.__http_session.auth = HTTPBasicAuth(username=self.__client_id, password=self.__client_secret)
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

    def get_credentials(self) -> BeyondTrustApiCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data="grant_type=client_credentials",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60,
            )
            response.raise_for_status()

            api_credentials: dict = response.json()

            credentials = BeyondTrustApiCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
