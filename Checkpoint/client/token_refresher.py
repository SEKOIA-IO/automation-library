"""Contains token refresher."""

import asyncio
import time
from asyncio import Lock
from contextlib import asynccontextmanager
from enum import Enum
from typing import AsyncGenerator, ClassVar

from cashews import Cache
from loguru import logger
from pydantic.v1 import BaseModel
from sekoia_automation.aio.helpers.http.token_refresher import GenericTokenRefresher, RefreshedToken


class CheckpointServiceType(str, Enum):
    """
    Enum that defines possible service types.
    Mapping between what you see during new API key onboarding.
    https://sc1.checkpoint.com/documents/Infinity_Portal/WebAdminGuides/EN/Infinity-Portal-Admin-Guide/Content/Topics-Infinity-Portal/API-Keys.htm?cshid=ID006
    """

    HARMONY_MOBILE = "harmony_mobile"


class CheckpointToken(BaseModel):
    """Model that represent token information."""

    token: str
    csrf: str
    expires: str
    expiresIn: int


# Setup cache to use memory with check interval 1 second and size 1
_cache = Cache()
_cache.setup("mem://?check_interval=1&size=1")


class CheckpointTokenRefresher(GenericTokenRefresher[RefreshedToken[CheckpointToken]]):
    """The Checkpoint token refresher implementation."""

    _instances: ClassVar[dict[str, "CheckpointTokenRefresher"]] = {}
    _locks: ClassVar[dict[str, Lock]] = {}

    def __init__(
        self,
        client_id: str,
        secret_key: str,
        auth_url: str,
        ttl_delta: int = 30,
        cache_key: str | None = None,
    ) -> None:
        """
        Initialize CheckpointTokenRefresher.

        Args:
            client_id: str
            secret_key: str
            auth_url: str
        """
        super().__init__()
        self.client_id = client_id
        self.secret_key = secret_key
        self.auth_url = auth_url
        self.ttl_delta = ttl_delta
        self.cache_key: str = cache_key or f"checkpoint_token_{client_id}"

    @classmethod
    async def get_instance(
        cls,
        client_id: str,
        secret_key: str,
        auth_url: str,
        service_type: CheckpointServiceType,
    ) -> "CheckpointTokenRefresher":
        """
        Get instance of CheckpointTokenRefresher.

        Totally safe to use in async environment. Use lock to prevent multiple
        instances creation. Get instance from cls._instances if it already exists
        based on client_id, secret_key and auth_url.

        Args:
            client_id: str
            secret_key: str
            auth_url: str
            service_type: CheckpointServiceType
        Returns:
            CheckpointTokenRefresher:
        """
        refresher_unique_key = str((client_id, secret_key, auth_url, service_type))
        if not cls._locks.get(refresher_unique_key):
            cls._locks[refresher_unique_key] = asyncio.Lock()

        if not cls._instances.get(refresher_unique_key):
            async with cls._locks[refresher_unique_key]:
                if not cls._instances.get(refresher_unique_key):
                    cls._instances[refresher_unique_key] = CheckpointTokenRefresher(
                        client_id, secret_key, auth_url, cache_key=refresher_unique_key
                    )

        return cls._instances[refresher_unique_key]

    async def get_token(self) -> RefreshedToken[CheckpointToken]:
        """
        Get token from server.

        Returns:
            RefreshedToken[CheckpointToken]:
        """
        logger.info("Get new auth token at {}", time.time())
        data = {"clientId": self.client_id, "accessKey": self.secret_key}

        async with self.session().post(url=self.auth_url, json=data) as response:
            result = await response.json()
            data = result.get("data", {})
            if not result.get("success") or not result.get("data"):
                raise ValueError("Failed to get token from server. Invalid response : {0}".format(result))

            return RefreshedToken(
                token=CheckpointToken(**data),
                created_at=int(time.time()),
                ttl=int(data.get("expiresIn", 0)),
            )

    @asynccontextmanager
    async def with_access_token(self) -> AsyncGenerator[RefreshedToken[CheckpointToken], None]:
        """
        Get access token.

        Yields:
            RefreshedTokenT:
        """
        cached_token: RefreshedToken[CheckpointToken] | None = await _cache.get(self.cache_key)
        if cached_token is None:
            cached_token = await self.get_token()
            ttl = cached_token.ttl - self.ttl_delta  # 30 seconds by default before token expires
            if ttl >= 1:
                logger.info("Cache new token with ttl {}", ttl)
                await _cache.set(self.cache_key, cached_token, expire=ttl)
            else:
                logger.info("Token is not cached because result ttl is less than 1 second")

        if not cached_token:
            raise ValueError("Token can not be initialized")

        yield cached_token

    async def mark_token_invalid(self) -> None:
        await self.close()
        await _cache.delete(self.cache_key)

    async def close(self) -> None:
        """
        Close the refresher.
        """
        await super().close()
        await _cache.clear()
        if self._session:
            await self._session.close()
