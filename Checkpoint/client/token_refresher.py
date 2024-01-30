"""Contains token refresher."""

import asyncio
import time
from asyncio import Lock
from enum import Enum
from typing import ClassVar

from loguru import logger
from pydantic import BaseModel
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


class CheckpointTokenRefresher(GenericTokenRefresher[RefreshedToken[CheckpointToken]]):
    """The Checkpoint token refresher implementation."""

    _instances: ClassVar[dict[str, "CheckpointTokenRefresher"]] = {}
    _locks: ClassVar[dict[str, Lock]] = {}

    def __init__(self, client_id: str, secret_key: str, auth_url: str) -> None:
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
                        client_id,
                        secret_key,
                        auth_url,
                    )

        return cls._instances[refresher_unique_key]

    async def get_token(self) -> RefreshedToken[CheckpointToken]:
        """
        Get token from server.

        Returns:
            RefreshedToken[CheckpointToken]:
        """
        logger.info("Get new auth token")
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
