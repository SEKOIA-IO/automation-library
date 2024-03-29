from datetime import datetime, timedelta
from typing import Any

import requests
from requests import PreparedRequest
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    def __init__(self, auth_url: str, client_id: str, client_secret: str) -> None:
        self.__auth_url = auth_url
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__api_credentials: dict[str, Any] | None = None

        self.__http_session = requests.Session()
        self.__http_session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                )
            ),
        )

    def get_authorization(self) -> str:
        """
        Returns the access token and uses the OAuth2 to compute it if required
        """

        if (
            self.__api_credentials is None
            or datetime.utcnow() + timedelta(seconds=300) >= self.__api_credentials["expires_in"]
        ):
            current_dt = datetime.utcnow()
            response = self.__http_session.post(
                url=self.__auth_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": "m365.api.read",
                    "client_id": self.__client_id,
                    "client_secret": self.__client_secret,
                },
                timeout=60,
            )
            response.raise_for_status()

            api_credentials: dict[str, Any] = response.json()
            # convert expirations into datetime
            api_credentials["expires_in"] = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = api_credentials

        return f"{self.__api_credentials['token_type'].title()} {self.__api_credentials['access_token']}"

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Authorization"] = self.get_authorization()
        return request
