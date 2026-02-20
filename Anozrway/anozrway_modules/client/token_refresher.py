from __future__ import annotations

import time

import aiohttp
from pydantic.v1 import BaseModel
from sekoia_automation.http.aio.token_refresher import GenericTokenRefresher, RefreshedToken

from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError


class AnozrwayOAuthToken(BaseModel):
    access_token: str


class AnozrwayTokenRefresher(GenericTokenRefresher[RefreshedToken[AnozrwayOAuthToken]]):
    """OAuth2 client-credentials token refresher for Anozrway API."""

    def __init__(self, client_id: str, client_secret: str, token_url: str, timeout: int = 30) -> None:
        super().__init__()
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_token(self) -> RefreshedToken[AnozrwayOAuthToken]:
        if not self._client_id or not self._client_secret:
            raise AnozrwayAuthError("Missing anozrway_client_id / anozrway_client_secret in module configuration")

        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        async with self.session().post(
            self._token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
            raise_for_status=False,
        ) as resp:
            status = resp.status
            text = await resp.text()

            if status == 401:
                raise AnozrwayAuthError(f"Token exchange unauthorized: {text}")

            if status != 200:
                raise AnozrwayError(f"Token request failed ({status}): {text}")

            token_data = await resp.json(content_type=None)

        token = token_data.get("access_token")
        if not token:
            raise AnozrwayError(f"OAuth2 response missing access_token: {token_data}")

        expires_in = int(token_data.get("expires_in", 3600))
        return RefreshedToken(
            token=AnozrwayOAuthToken(access_token=token),
            created_at=int(time.time()),
            ttl=max(60, expires_in - 300),
        )
