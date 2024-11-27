from datetime import datetime, timedelta
from threading import Lock

import requests
from pyrate_limiter import Limiter
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class MimecastCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class ApiKeyAuthentication(AuthBase):
    AUTH_URL = "https://api.services.mimecast.com/oauth/token"

    def __init__(self, client_id: str, client_secret: str, limiter: Limiter, nb_retries: int = 5) -> None:
        self.__client_id = client_id
        self.__client_secret = client_secret

        self.__credentials: MimecastCredentials | None = None
        self.__http_session = requests.Session()
        self.__http_session.mount(
            "https://",
            LimiterAdapter(
                limiter=limiter,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

        self.__lock = Lock()

    def get_credentials(self) -> MimecastCredentials:
        self.__lock.acquire()

        current_dt = datetime.utcnow()
        if self.__credentials is None or current_dt + timedelta(seconds=300) >= self.__credentials.expires_at:
            response = self.__http_session.post(
                url=self.AUTH_URL,
                data=f"client_id={self.__client_id}&client_secret={self.__client_secret}&grant_type=client_credentials",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60,
            )
            response.raise_for_status()

            api_credentials: dict = response.json()

            credentials = MimecastCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__credentials = credentials

        self.__lock.release()

        return self.__credentials

    def __call__(self, request):
        request.headers["Authorization"] = self.get_credentials().authorization

        return request
