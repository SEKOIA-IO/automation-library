from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase, HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry


class CyberArkApiCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class AuthorizationFailedException(BaseException):
    pass


class CyberArkApiAuthentication(AuthBase):
    def __init__(
        self,
        auth_base_url: str,
        application_id: str,
        client_id: str,
        client_secret: str,
        api_key: str,
        ratelimit_per_second: int = 10,
    ) -> None:
        self.__authorization_url = urljoin(auth_base_url, f"oauth2/token/{application_id}")
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__api_key = api_key
        self.__api_credentials: CyberArkApiCredentials | None = None

        self.__http_session = requests.Session()
        self.__http_session.auth = HTTPBasicAuth(username=self.__client_id, password=self.__client_secret)
        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                ),
            ),
        )

    def __handle_response_error(self, response: requests.Response) -> None:
        """
        Handle errors from CyberArk API authentication responses.
        """
        if response.status_code in [400, 401, 403]:
            error_code: str | None = None
            error_description: str | None = None

            try:
                error = response.json()
                error_code = error.get("error")
                error_description = error.get("error_description")
            finally:
                message = f"Request to CyberArk API failed with status {response.status_code} - {response.reason}"
                if error_code:
                    message += f" error_code={error_code}"
                if error_description:
                    message += f" error_description={error_description}"

                raise AuthorizationFailedException(message)
        else:
            response.raise_for_status()

    def get_credentials(self) -> CyberArkApiCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=300) >= self.__api_credentials.expires_at:
            response = self.__http_session.post(
                url=self.__authorization_url,
                data="grant_type=client_credentials&scope=isp.audit.events:read",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60,
            )
            self.__handle_response_error(response)

            api_credentials: dict = response.json()

            credentials = CyberArkApiCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization
        request.headers["x-api-key"] = self.__api_key
        return request
