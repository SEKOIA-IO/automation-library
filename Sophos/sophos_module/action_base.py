from abc import ABC
from functools import cached_property
from typing import Any, Callable
from urllib.parse import urljoin

from sekoia_automation.action import Action

from .base import SophosModule
from .client import SophosApiClient
from .client.auth import SophosApiAuthentication
from .logging import get_logger

logger = get_logger()


class SophosEDRAction(Action, ABC):
    module: SophosModule

    @cached_property
    def client(self) -> SophosApiClient:
        auth = SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return SophosApiClient(auth=auth)

    @cached_property
    def region_base_url(self) -> str:
        url = urljoin(self.module.configuration.api_host, "whoami/v1")
        response = self.client.get(url).json()

        return str(response["apiHosts"]["dataRegion"])

    def call_endpoint(
        self, method: str, url: str, data: dict[str, Any] | None = None, use_region_url: bool = False
    ) -> Any:
        assert method.lower() in ("get", "post", "patch")

        base_url = self.region_base_url if use_region_url else self.module.configuration.api_host
        url = urljoin(base_url, url)

        func: Callable[[Any], Any]
        if method.lower() == "post":
            func = self.client.post

        elif method.lower() == "patch":
            func = self.client.patch

        else:
            func = self.client.get

        response = func(url=url, json=data)

        if response.ok:
            return response.json()

        else:
            raw = response.json()
            logger.error(
                f"Error {response.status_code}",
                error=raw.get("error"),
                message=raw.get("message"),
                corellation_id=raw.get("correlationId"),
                code=raw.get("code"),
                created_at=raw.get("createdAt"),
                request_id=raw.get("requestId"),
                doc_url=raw.get("docUrl"),
            )
            response.raise_for_status()

        return {}
