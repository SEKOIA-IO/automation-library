import time
from datetime import datetime, timedelta
from threading import Event
from typing import Callable
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase, HTTPBasicAuth

from withsecure.client.exceptions import AuthenticationError
from withsecure.constants import API_AUTH_MAX_ATTEMPT, API_AUTH_SECONDS_BETWEEN_ATTEMPTS, API_BASE_URL, API_TIMEOUT
from withsecure.helpers import human_readable_api_exception

API_AUTHENTICATION_URL = urljoin(API_BASE_URL, "/as/token.oauth2")


class OAuthAuthentication(AuthBase):
    """
    Implements a Requests's authentification for WithSecure API
    """

    client_id: str
    secret: str
    grant_type: str
    scope: str

    access_token_value: str | None
    access_token_valid_until: datetime | None

    def __init__(
        self,
        client_id: str,
        secret: str,
        grant_type: str,
        scope: str,
        stop_event: Event,
        log_cb: Callable[[str, str], None],
    ):
        self.client_id = client_id
        self.secret = secret
        self.grant_type = grant_type
        self.scope = scope

        # authentication material
        self.access_token_value = None
        self.access_token_valid_until = None

        self.log_cb = log_cb
        self._stop_event = stop_event

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
                self.log_cb("Failed to authenticate on the WithSecure API, stopping the connector", "critical")
                return ""

        return self.access_token_value

    def authenticate(self) -> None:
        """
        Authenticate on the API of WithSecure to obtain an access token.

        An retry mechanism is implemented but invalid credentials
        error will instantly stop the process.

        :raises AuthenticationError if it failed to authenticate due to permissions or credentials
        """
        i_attempt = 0
        while not self._stop_event.is_set():
            i_attempt += 1
            if 0 < API_AUTH_MAX_ATTEMPT < i_attempt:
                break

            try:
                auth_response = requests.post(
                    url=API_AUTHENTICATION_URL,
                    auth=HTTPBasicAuth(self.client_id, self.secret),
                    timeout=API_TIMEOUT,
                    data={"grant_type": self.grant_type, "scope": self.scope},
                )
                if auth_response.status_code == 200:
                    # reads the server response
                    payload = auth_response.json()
                    self.access_token_value = payload["access_token"]
                    self.access_token_valid_until = (
                        datetime.utcnow() - timedelta(minutes=1) + timedelta(seconds=payload["expires_in"])
                    )
                    return
                elif auth_response.status_code in (400, 401):
                    # reads the server response
                    payload = auth_response.json()
                    self.log_cb(
                        f"Authentication on WithSecure API failed with error: '{payload['error_description']}'",
                        "error",
                    )
                    raise AuthenticationError()
                else:
                    auth_response.raise_for_status()
            except AuthenticationError:
                raise
            except Exception as error:
                self.log_cb(
                    (
                        f"Authentication attempt failed: "
                        f"{human_readable_api_exception(error)}. Will retry in {API_AUTH_SECONDS_BETWEEN_ATTEMPTS} seconds."
                    ),
                    "warning",
                )
                time.sleep(API_AUTH_SECONDS_BETWEEN_ATTEMPTS)

        raise AuthenticationError()
