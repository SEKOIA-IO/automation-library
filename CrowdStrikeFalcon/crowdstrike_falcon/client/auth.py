from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase


class CrowdStrikeFalconApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class CrowdStrikeFalconApiAuthentication(AuthBase):
    """
    Implements a Requests's authentification for CrowdStrike Falcon API
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        module_name: str | None = None,
        module_version: str | None = None
    ):
        self.__authorization_url = urljoin(base_url, "/oauth2/token")
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__api_credentials: CrowdStrikeFalconApiCredentials | None = None
        self.__http_session = requests.Session()

        if module_name and module_version:
            self.__http_session.headers.update(
                {
                    "User-Agent": "sekoiaio-connector/{0}-{1}".format(module_name, module_version),
                }
            )

        self.__http_session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                )
            ),
        )

    def get_credentials(self) -> CrowdStrikeFalconApiCredentials:
        """
        Return CrowdStrike Credentials for the API
        """
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data={
                    "client_id": self.__client_id,
                    "client_secret": self.__client_secret,
                },
            )

            response.raise_for_status()

            credentials = CrowdStrikeFalconApiCredentials()

            api_credentials: dict = response.json()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        return request
