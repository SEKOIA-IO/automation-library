import datetime
from typing import Any

import requests
from dateutil.parser import isoparse
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter, PreparedRequest


class LaceworkCredentials:
    token: str
    expiresAt: datetime.datetime

    @property
    def authorization(self) -> str:
        return f"Bearer {self.token}"


class LaceworkAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Lacework API
    """

    def __init__(
        self,
        lacework_url: str,
        access_key: str,
        secret_key: str,
        default_headers: dict[str, str] | None = None,
        ratelimit_per_hour: int = 480,
    ):
        self.__lacework_url = lacework_url
        self.__access_key = access_key
        self.__secret_key = secret_key
        self.__api_credentials: LaceworkCredentials | None = None
        self.__http_session = requests.Session()

        if default_headers:
            self.__http_session.headers.update(default_headers)

        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                per_hour=ratelimit_per_hour,
            ),
        )

    def get_credentials(self) -> LaceworkCredentials:
        """
        Return Lacework Credentials for the API
        """
        current_dt = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (
            self.__api_credentials.expiresAt.replace(tzinfo=datetime.timezone.utc)
            if self.__api_credentials
            else current_dt
        )

        if self.__api_credentials is None or current_dt + datetime.timedelta(seconds=3600) >= expires_at:
            response = self.__http_session.post(
                url=f"https://{self.__lacework_url}/api/v2/access/tokens",
                headers={"X-LW-UAKS": self.__secret_key, "Content-Type": "application/json"},
                json={"keyId": self.__access_key, "expiryTime": 3600},
            )

            response.raise_for_status()

            credentials = LaceworkCredentials()

            api_credentials: dict[Any, Any] = response.json()
            credentials.token = api_credentials["token"]
            credentials.expiresAt = isoparse(api_credentials["expiresAt"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Authorization"] = self.get_credentials().authorization
        request.headers["Content-Type"] = "application/json"
        return request
