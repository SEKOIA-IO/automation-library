import logging

import requests
from requests.auth import AuthBase

from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class ApiKeyAuthentication(AuthBase):
    def __init__(self, hostname: str, login: str, password: str):
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
            self.authenticate()

        return f"{self._account_login}:{self._token}"

    def authenticate(self):
        auth_response = requests.post(
            url=f"{self.__hostname}/rest/v3.0/login/login",
            headers={
                "Content-type": "application/json",
                "Accept": "application/json",
            },
            json={"login": self.__login, "password": self.__password},
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
            payload = auth_response.json()
            logger.error(payload)

            raise AuthenticationError(payload)

        raise AuthenticationError

    @property
    def account_id(self):
        return self._account_id
