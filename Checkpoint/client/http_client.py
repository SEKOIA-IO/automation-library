"""Contains http client."""
from datetime import datetime

from aiolimiter import AsyncLimiter
from loguru import logger
from sekoia_automation.aio.helpers.http.http_client import HttpClient

from .schemas.harmony_mobile_schemas import HarmonyMobileSchema
from .token_refresher import CheckpointServiceType, CheckpointTokenRefresher


class CheckpointHttpClient(HttpClient):
    """The Checkpoint http client implementation."""

    def __init__(
        self,
        client_id: str,
        secret_key: str,
        auth_url: str,
        base_url: str,
        max_rate: float | None = None,
        time_period: float | None = None,
        rate_limiter: AsyncLimiter | None = None,
    ) -> None:
        """
        Initialize CheckpointHttpClient.

        Args:
            client_id: str
            secret_key: str
            auth_url: str
            base_url: str
            max_rate: float | None
            time_period: float | None
            rate_limiter: AsyncLimiter | None
        """
        super().__init__(max_rate, time_period, rate_limiter)
        self.client_id = client_id
        self.secret_key = secret_key
        self.auth_url = auth_url
        self.base_url = base_url

    async def get_token_refresher(self, service_type: CheckpointServiceType) -> CheckpointTokenRefresher:
        """
        Get CheckpointTokenRefresher.

        Args:
            service_type: CheckpointServiceType

        Returns:
            CheckpointTokenRefresher:
        """
        return await CheckpointTokenRefresher.get_instance(
            self.client_id,
            self.secret_key,
            self.auth_url,
            service_type,
        )

    async def get_harmony_mobile_alerts(
        self, start_from: datetime = datetime.now(), limit: int = 100
    ) -> list[HarmonyMobileSchema]:
        """
        Get Harmony Mobile alerts.

        Args:
            start_from: datetime
            limit: int

        Returns:
            list[HarmonyMobileSchema]:
        """
        url = "{0}/app/SBM/external_api/v3/alert/".format(self.base_url)
        formatted_start_date = start_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        logger.info("Fetch events with limit {0} starting from: {1}", limit, formatted_start_date)

        params = {
            "backend_last_updated__gte": formatted_start_date,
            "limit": limit,
        }

        token_refresher = await self.get_token_refresher(CheckpointServiceType.HARMONY_MOBILE)

        logger.info(url)

        async with token_refresher.with_access_token() as token:
            async with self.session() as session:
                async with session.get(
                    url=url,
                    headers={"Authorization": f"Bearer {token.token.token}"},
                    params=params,
                ) as response:
                    result = await response.json()

        if result.get("objects") is None:
            logger.error("Failed to get events from server. Invalid response : {0}", result)

            return []

        return [HarmonyMobileSchema(**data) for data in result["objects"]]
