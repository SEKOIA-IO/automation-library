import requests
from requests import PreparedRequest
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    def __init__(self, hostname: str, login: str, password: str) -> None:
        self.__hostname = hostname
        self.__login = login
        self.__password = password
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

        self._token: str | None = None
        self._account_id: int | None = None
        self._user_id: int | None = None
        self._account_login: str | None = None

    def authenticate(self) -> None:
        try:
            response = self.__http_session.post(
                url=f"{self.__hostname}/rest/v3.0/login/login",
                headers={
                    "Content-type": "application/json",
                    "Accept": "application/json",
                },
                json={"login": self.__login, "password": self.__password},
                timeout=60,
            )
        except requests.Timeout as error:
            raise TimeoutError from error

        response.raise_for_status()

        self._token = response.headers.get("x-vrc-authorization")
        account = next(
            account for account in response.json().get("accounts", []) if account.get("accountEmail") == self.__login
        )
        self._account_id = account.get("accountId")
        if account.get("accountType", "user").upper() in ["QUARANTINE", "ADMINISTRATOR"]:
            self._user_id = account.get("userId")

        self._account_login = account.get("accountLogin")

    def get_authorization_header(self) -> str:
        return f"{self._account_login}:{self._token}"

    @property
    def account_id(self) -> int | None:
        return self._user_id or self._account_id

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["x-vrc-authorization"] = self.get_authorization_header()

        return request
