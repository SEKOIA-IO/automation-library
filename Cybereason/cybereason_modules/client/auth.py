from datetime import datetime, timedelta
from posixpath import join as urljoin

import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase
from requests.cookies import merge_cookies

from cybereason_modules.exceptions import LoginFailureError, TimeoutError
from cybereason_modules.helpers import validate_response_not_login_failure


class CybereasonApiCredentials:
    session_id: str | None
    expires_at: datetime


class CybereasonApiAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Cybereason API
    """

    def __init__(self, base_url: str, username: str, password: str):
        self.__authorization_url = urljoin(base_url, "login.html")
        self.__username = username
        self.__password = password
        self.__api_credentials: CybereasonApiCredentials | None = None
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

    def get_credentials(self) -> CybereasonApiCredentials:
        """
        Return Cybereason Credentials for the API
        """
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            try:
                response = self.__http_session.post(
                    url=self.__authorization_url,
                    data={
                        "username": self.__username,
                        "password": self.__password,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    verify=True,
                    timeout=60,
                )
            except requests.Timeout as error:
                raise TimeoutError(self.__authorization_url) from error

            response.raise_for_status()

            if not validate_response_not_login_failure(response):
                raise LoginFailureError(self.__authorization_url)

            credentials = CybereasonApiCredentials()
            credentials.session_id = self.__http_session.cookies.get("JSESSIONID")
            credentials.expires_at = current_dt + timedelta(hours=8)
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.prepare_cookies(merge_cookies(request._cookies, {"JSESSIONID": self.get_credentials().session_id}))
        return request
