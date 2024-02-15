"""Contains http client."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from posixpath import join as urljoin

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
    ) -> AsyncGenerator[list[HarmonyMobileSchema], None]:
        """
        Get Harmony Mobile alerts.

        Args:
            start_from: datetime
            limit: int

        Returns:
            AsyncGenerator[list[HarmonyMobileSchema]]:
        """
        base_url = urljoin(self.base_url, "app/SBM")
        formatted_start_date = start_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        endpoint = f"/external_api/v3/alert/?backend_last_updated__gte={formatted_start_date}&limit={limit}"
        logger.info("Fetch events with limit {0} starting from: {1}", limit, formatted_start_date)

        token_refresher = await self.get_token_refresher(CheckpointServiceType.HARMONY_MOBILE)

        while endpoint is not None:
            async with token_refresher.with_access_token() as token:
                async with self.session() as session:
                    async with session.get(
                        url=f"{base_url}{endpoint}",
                        headers={"Authorization": f"Bearer {token.token.token}"},
                    ) as response:
                        response_json = await response.json()

            if response_json.get("objects") is None:
                logger.error("Failed to get events from server. Invalid response : {0}", response_json)

                return

            yield [
                HarmonyMobileSchema(
                    **{
                        **data,
                        "event_timestamp": self.parse_date(data.get("event_timestamp")),
                        "backend_last_updated": self.parse_date(data.get("backend_last_updated")),
                    }
                )
                for data in response_json["objects"]
            ]

            endpoint = response_json.get("meta", {}).get("next")

    @staticmethod
    def parse_date(value: str | None) -> datetime | None:
        """
        Parse date.

        Swagger says that it should have "%m/%d/%Y %H:%M:%S" but all other values that we pass are in ISO format
        So we try to parse it as ISO and if it fails we parse it as "%m/%d/%Y %H:%M:%S"
        See 200 response here:
        https://app.swaggerhub.com/apis-docs/Check-Point/harmony-mobile/1.0.0-oas3#/Events/GetAlerts

        Also, sometimes it can be `No data` value.

        Args:
            value: str

        Returns:
            datetime | None:
        """
        if value is None:
            return None

        try:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

        except ValueError:
            try:
                return datetime.strptime(value, "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone.utc)

            except ValueError:
                logger.warning("Failed to parse date: {0}. It is not either ISO or `%m/%d/%Y %H:%M:%S` format", value)

                return None
