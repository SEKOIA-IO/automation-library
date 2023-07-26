from typing import Callable

import requests
from requests.auth import AuthBase

from .exceptions import AuthenticationError


class ApiKeyAuthentication(AuthBase):
    def __init__(self, hostname: str, login: str, password: str, log_callback: Callable):
        self.log_cb = log_callback

        self.__hostname = hostname
        self.__login = login
        self.__password = password

        self._token: str | None = None
        self._account_id: int | None = None
        self._account_login: str | None = None

    def __call__(self, request):
        request.headers["x-vrc-authorization"] = self.access_token
        return request

    @property
    def access_token(self):
        if self._token is None or self._account_login is None:
            try:
                self.authenticate()

            except Exception:
                self.log_cb("Failed to authenticate on the Vade Cloud API", "critical")
                return ""

        return f"{self._account_login}:{self._token}"

    def authenticate(self):
        try:
            auth_response = requests.post(
                url=f"{self.__hostname}/rest/v3.0/login/login",
                headers={
                    "Content-type": "application/json",
                    "Accept": "application/json",
                },
                json={"login": self.__login, "password": self.__password},
                timeout=60,
            )

            if auth_response.status_code == 200:
                self._token = auth_response.headers.get("x-vrc-authorization")
                account = next(
                    account
                    for account in auth_response.json().get("accounts", [])
                    if account.get("accountEmail") == self.__login
                )
                self._account_id = account.get("accountId")
                self._account_login = account.get("accountLogin")

                return

            elif auth_response.status_code in (400, 401):
                payload = auth_response.text
                self.log_cb(
                    f"Authentication on Vade Cloud API failed with error: '{payload}'",
                    "error",
                )

                raise AuthenticationError(payload)

            else:
                auth_response.raise_for_status()

        except AuthenticationError:
            raise

        except Exception as error:
            self.log_cb(
                f"Authentication attempt failed: {error}",
                "error",
            )

        raise AuthenticationError

    @property
    def account_id(self):
        return self._account_id
