from datetime import datetime, timedelta

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from .retry import Retry


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
