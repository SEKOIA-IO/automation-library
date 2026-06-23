import json
from functools import cached_property
from typing import Any, cast

import requests
from pydantic import BaseModel, Field
from requests import Response
from sekoia_automation.action import Action
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules import NetskopeModule
from netskope_modules.logging import get_logger

logger = get_logger()


class NetskopeActionArguments(BaseModel):
    api_token: str = Field(..., description="API token for authentication")


class NetskopeAction(Action):
    module: NetskopeModule
    _api_token: str | None = None

    @property
    def api_token(self) -> str:
        if not self._api_token:
            raise ModuleConfigurationError("The API token is undefined. Please set it in action arguments")
        return self._api_token

    def initialize_action_arguments(self, arguments: NetskopeActionArguments) -> None:
        self._api_token = arguments.api_token

    @staticmethod
    def normalize_urls(items: list[str], sort_items: bool = True) -> list[str]:
        """
        Return a deduplicated blocklist with optional alphabetical sorting.
        Empty values are discarded.
        """
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in items:
            if not item:
                continue

            normalized = item.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            cleaned.append(normalized)

        if sort_items:
            return sorted(cleaned, key=str.lower)

        return cleaned

    @staticmethod
    def extract_urls(blocklist: dict) -> list[str]:
        """
        Extract URLs from a Netskope blocklist payload.
        """
        data = blocklist.get("data", {})
        urls = data.get("urls", [])
        return [url for url in urls if isinstance(url, str)]

    def get_blocklist(self, blocklist_id: str | int) -> dict[str, Any]:
        """
        Retrieve the current blocklist payload from Netskope.
        """
        return cast(dict[str, Any], self.execute_request("GET", f"api/v2/policy/urllist/{blocklist_id}"))

    @cached_property
    def base_url(self) -> str:
        base_url = None

        # Preferred path: validated module configuration model
        try:
            configuration = self.module.configuration
            if isinstance(configuration, dict):
                base_url = configuration.get("base_url")
            else:
                base_url = getattr(configuration, "base_url", None)
        except ModuleConfigurationError:
            # Backward-compatibility path: read raw config when model validation fails
            raw_configuration = self.module.load_config(self.module.MODULE_CONFIGURATION_FILE_NAME, "json")
            if isinstance(raw_configuration, dict):
                base_url = raw_configuration.get("base_url")

        if not base_url:
            raise ModuleConfigurationError("The base url is undefined. Please set the url of the Netskope API")
        return base_url.rstrip("/")

    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            logger.error(
                "Failed request to Netskope API",
                status_code=response.status_code,
                reason=response.reason,
                error=response.content,
            )

            message = f"Request to Netskope API failed with status {response.status_code} - {response.reason}"
            self.log(message=message, level="error")
            response.raise_for_status()

        try:
            json_body = response.json()
            if "error" in json_body:
                error_message = json_body["error"].get("message", "Unknown error")
                logger.error(
                    "Netskope API returned an error",
                    error=error_message,
                    status_code=response.status_code,
                )
                raise ValueError(f"Netskope API returned an error: {error_message}")
        except json.JSONDecodeError:
            pass  # Response might not be JSON

    def deploy_blocklist_changes(self) -> Any:
        """
        Deploy blocklist changes to make them active.
        """
        return self.execute_request("POST", "api/v2/policy/urllist/deploy")

    def execute_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Execute a request to the Netskope API.
        """
        url = f"{self.base_url}/{endpoint}"
        extra_headers = kwargs.pop("headers", {})
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            **extra_headers,
        }

        response = requests.request(method, url, headers=headers, **kwargs)
        self._handle_response_error(response)

        return response.json() if response.content else {}
