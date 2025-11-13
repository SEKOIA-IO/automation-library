from datetime import datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase

from sophos_module.logging import get_logger
from sophos_module.client.exceptions import SophosApiAuthenticationError
from sophos_module.client.helpers import retry

logger = get_logger()


class SophosApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime
    tenancy_type: str
    tenancy_id: str
    api_url: str

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"

    @property
    def tenancy_header(self) -> dict[str, str]:
        return {f"X-{self.tenancy_type.title()}-ID": self.tenancy_id}


class SophosApiAuthentication(AuthBase):
    def __init__(self, api_host: str, authorization_url: str, client_id: str, client_secret: str) -> None:
        self.__api_host = api_host
        self.__authorization_url = authorization_url
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.api_credentials: SophosApiCredentials | None = None
        self.__http_session = requests.Session()
        self.__http_session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )
            ),
        )

    @retry()
    def __get_token(self) -> Any:
        """
        Get OAuth2 token from Sophos API
        """
        # Make the POST request to get the token
        response = self.__http_session.post(
            url=self.__authorization_url,
            data={
                "grant_type": "client_credentials",
                "scope": "token",
                "client_id": self.__client_id,
                "client_secret": self.__client_secret,
            },
        )

        # Log the response status
        logger.info(
            "OAuth2 server responded",
            status_code=response.status_code,
            reason=response.reason,
        )

        # Handle authentication errors
        if response.status_code in {400, 401, 403}:
            raise SophosApiAuthenticationError("Authentication failed. Check your client_id and client_secret.")

        # Raise for other HTTP errors
        response.raise_for_status()

        # Return the successful response
        return response.json()

    @retry()
    def __whoami(self, credentials: SophosApiCredentials) -> Any:
        """
        Call the Whoami endpoint to get tenancy information
        """
        # Get the whoami
        response = self.__http_session.get(
            url=f"{self.__api_host}/whoami/v1",
            headers={"Authorization": credentials.authorization},
        )

        # Log the response status
        logger.info(
            "Whoami endpoint responded",
            status_code=response.status_code,
            reason=response.reason,
        )

        # Handle authentication errors
        if response.status_code in {400, 401, 403}:
            raise SophosApiAuthenticationError("The Whoami call failed. Check your client_id and client_secret.")

        # Raise for other HTTP errors
        response.raise_for_status()

        # Return the successful response
        return response.json()

    def get_credentials(self) -> SophosApiCredentials:
        """
        Return Sophos Credentials for the API
        """
        current_dt = datetime.utcnow()

        if self.api_credentials is None or current_dt + timedelta(seconds=300) >= self.api_credentials.expires_at:
            # Initialize credentials
            credentials: SophosApiCredentials = SophosApiCredentials()

            # Get OAuth2 token
            api_credentials: dict[str, Any] = self.__get_token()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])

            whoami: dict[str, Any] = self.__whoami(credentials)
            credentials.tenancy_type = whoami["idType"]
            credentials.tenancy_id = whoami["id"]
            credentials.api_url = whoami["apiHosts"].get("dataRegion") or whoami["apiHosts"]["global"]
            self.api_credentials = credentials

        return self.api_credentials

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        credentials = self.get_credentials()
        request.headers["Authorization"] = credentials.authorization
        request.headers.update(credentials.tenancy_header)

        return request
