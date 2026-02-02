from datetime import datetime, timedelta

import httpx
from httpx import Auth, Request, Response
from httpx_ratelimiter import LimiterTransport


class AuthorizationError(Exception):
    pass


class ApiKeyAuthentication(Auth):
    def __init__(self, token: str):
        self.__token = token

    def auth_flow(self, request: Request):
        request.headers["Authorization"] = f"Bearer {self.__token}"
        yield request


class UbikaCloudProtectorNextGenCredentials:
    token_type: str
    access_token: str
    expires_at: datetime

    @property
    def authorization(self) -> str:
        return f"{self.token_type.title()} {self.access_token}"


class UbikaCloudProtectorNextGenAuthentication(Auth):
    def __init__(self, refresh_token: str, transport: httpx.BaseTransport) -> None:
        self.__authorization_url = "https://login.ubika.io/auth/realms/main/protocol/openid-connect/token"
        self.__refresh_token = refresh_token
        self.__api_credentials: UbikaCloudProtectorNextGenCredentials | None = None

        # Configure HTTPX client with rate limiting and http2 support
        self.__http_client = httpx.Client(
            http2=True,
            transport=transport,
            timeout=300.0,
        )

    def get_credentials(self) -> UbikaCloudProtectorNextGenCredentials:
        current_dt = datetime.utcnow()

        if self.__api_credentials is None or current_dt + timedelta(seconds=60) >= self.__api_credentials.expires_at:
            response: Response | None = None
            try:
                response = self.__http_client.post(
                    url=self.__authorization_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": "rest-api",
                        "refresh_token": self.__refresh_token,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                response.raise_for_status()

            except httpx.TimeoutException as timeout_exc:
                raise AuthorizationError(
                    "timeout_error", "The request to obtain a new access token timed out."
                ) from timeout_exc

            except httpx.HTTPStatusError as e:
                if response is None:
                    raise AuthorizationError(
                        "no_response", "No response received when requesting a new access token."
                    ) from e
                raw = response.json()
                raise AuthorizationError(raw["error"], raw["error_description"]) from e

            except httpx.RequestError as e:
                raise AuthorizationError(
                    "request_error", f"An error occurred while requesting a new access token : {e}"
                ) from e

            api_credentials: dict = response.json()

            credentials = UbikaCloudProtectorNextGenCredentials()
            credentials.token_type = api_credentials["token_type"]
            credentials.access_token = api_credentials["access_token"]
            credentials.expires_at = current_dt + timedelta(seconds=api_credentials["expires_in"])
            self.__api_credentials = credentials

        return self.__api_credentials

    def auth_flow(self, request: Request):
        request.headers["Authorization"] = self.get_credentials().authorization
        yield request

    def close(self):
        self.__http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
