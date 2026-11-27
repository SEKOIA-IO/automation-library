from abc import ABC
from collections.abc import Callable
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

from sekoia_automation.action import Action

from sophos_module.base import SophosModule
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.errors import format_http_error
from sophos_module.logging import get_logger

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

        func: Callable[..., Any]
        if method.lower() == "post":
            func = self.client.post

        elif method.lower() == "patch":
            func = self.client.patch

        else:
            func = self.client.get

        response = func(url=url, json=data)

        if not response.ok:
            # stable message for the user, with what to check (e.g. the role of the API credential)
            self.log(message=format_http_error("The Sophos API call failed", response), level="error")
            logger.error(
                "Sophos API call failed",
                method=method.upper(),
                url=url,
                status_code=response.status_code,
                response=response.text[:1000],
            )
            response.raise_for_status()

        return response.json()
