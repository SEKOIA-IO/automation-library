import time
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase, HTTPBasicAuth

from withsecure.client.exceptions import AuthenticationError
from withsecure.constants import API_AUTH_MAX_RETRY, API_BASE_URL, API_TIMEOUT


class OAuthAuthentication(AuthBase):
    """
    Implements a Requests's authentification for WithSecure API
    """

    client_id: str
    secret: str
    grant_type: str

    access_token_value: str | None
    access_token_valid_until: datetime | None

    def __init__(self, client_id: str, secret: str, grant_type: str, log_cb: Callable[[str, str], None]):
        self.client_id = client_id
        self.secret = secret
        self.grant_type = grant_type

        # authentication material
        self.access_token_value = None
        self.access_token_valid_until = None

        self.log_cb = log_cb

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self._get_access_token()}"
        return request

    def _get_access_token(self) -> str:
        """
        This method returns the API access token.
        If required, it triggers the OAuth auth flow to fetch or update the token
        """

        # trigger the authentication if required
        if (
            not self.access_token_value
            or not self.access_token_valid_until
            or self.access_token_valid_until < datetime.utcnow()
        ):
            # noinspection PyBroadException
            try:
                self.authenticate()
            except Exception:
                self.log_cb(
                    f"Failed to authenticate on the WithSecure API after {API_AUTH_MAX_RETRY} attempts", "critical"
                )
                return ""

        return self.access_token_value

    def authenticate(self) -> None:
        """
        Authenticate on the API of WithSecure to obtain an access token.

        A retry mechanism is implemented, if all attempts fail a critical log
        is raised which will stop the connector.

        :raises AuthenticationError if it failed to authenticate
        """

        for auth_attempt in range(API_AUTH_MAX_RETRY):
            try:
                auth_response = requests.post(
                    url=urljoin(API_BASE_URL, "/as/token.oauth2"),
                    auth=HTTPBasicAuth(self.client_id, self.secret),
                    timeout=API_TIMEOUT,
                )
                if auth_response.status_code == 200:
                    payload = auth_response.json()
                    self.access_token_value = payload["access_token"]
                    self.access_token_valid_until = (
                        datetime.utcnow() - timedelta(minutes=1) + timedelta(seconds=payload["expires_in"])
                    )
                    return None
            except requests.exceptions.ConnectionError as error:
                self.log_cb(
                    f"Authentication attempt {auth_attempt+1} failed with error '{error}'. Will retry in few seconds.",
                    "warning",
                )
                time.sleep(5)

        raise AuthenticationError()
