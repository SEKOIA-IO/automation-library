import time
from datetime import datetime, timedelta

import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class ZScalerZIACredentials:
    token: str
    expires_at: datetime


class ZscalerZIAAuthentication(AuthBase):
    def __init__(
        self, cloud_name: str, username: str, password: str, api_key: str, ratelimit_per_second: int = 10
    ) -> None:
        self.__base_url = f"https://zsapi.{cloud_name}/api/v1"
        self.__username = username
        self.__password = password
        self.__api_key = api_key

        self.__api_credentials: ZScalerZIACredentials | None = None
        self.__http_session = requests.Session()
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

    @property
    def base_url(self) -> str:
        return self.__base_url

    @staticmethod
    def obfuscate_api_key(api_key: str) -> tuple[int, str]:
        now = int(time.time() * 1000)
        n = str(now)[-6:]
        r = str(int(n) >> 1).zfill(6)
        key = ""
        for i in range(0, len(str(n)), 1):
            key += api_key[int(str(n)[i])]
        for j in range(0, len(str(r)), 1):
            key += api_key[int(str(r)[j]) + 2]

        return now, key

    def get_credentials(self) -> ZScalerZIACredentials:
        # Session timeout is changed via ZIA Admin Portal, and lies from 5 minutes to 600 minutes
        cookies_ttl = 5 * 60  # seconds
        current_dt = datetime.utcnow()

        if (
            self.__api_credentials is None
            or current_dt + timedelta(seconds=max(30, cookies_ttl // 5)) >= self.__api_credentials.expires_at
        ):
            timestamp, key = self.obfuscate_api_key(self.__api_key)
            payload = {
                "apiKey": key,
                "username": self.__username,
                "password": self.__password,
                "timestamp": timestamp,
            }

            url = f"{self.__base_url}/authenticatedSession"
            response = self.__http_session.post(url, json=payload)
            response.raise_for_status()

            credentials = ZScalerZIACredentials()
            credentials.token = response.cookies["JSESSIONID"]
            credentials.expires_at = current_dt + timedelta(seconds=cookies_ttl)

            self.__api_credentials = credentials

        return self.__api_credentials

    def __call__(self, request):
        request.headers["Cookie"] = "JSESSIONID=%s" % self.get_credentials().token
        return request
