import json
from functools import cached_property
from typing import Any, cast

import requests
from pydantic import BaseModel, Field
from requests import PreparedRequest, Response
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
    _last_api_request: dict[str, Any] | None = None

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

    def get_api_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint}"

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

    @staticmethod
    def _mask_headers(headers: dict[str, str] | None) -> dict[str, str]:
        if not headers:
            return {}

        masked = dict(headers)
        authorization_key = next((key for key in masked if key.lower() == "authorization"), None)
        if authorization_key:
            masked[authorization_key] = "Bearer ***"

        return masked

    def _serialize_request(self, prepared_request: PreparedRequest, kwargs: dict[str, Any]) -> dict[str, Any]:
        body: str | None = None
        if prepared_request.body is not None:
            if isinstance(prepared_request.body, bytes):
                body = prepared_request.body.decode("utf-8", errors="replace")
            else:
                body = str(prepared_request.body)

        normalized_headers: dict[str, str] = {}
        for key, value in (prepared_request.headers or {}).items():
            header_key = key.decode("utf-8", errors="replace") if isinstance(key, bytes) else str(key)
            header_value = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
            normalized_headers[header_key] = header_value

        request_snapshot = {
            "method": prepared_request.method,
            "url": prepared_request.url,
            "headers": self._mask_headers(normalized_headers),
        }

        if body is not None:
            request_snapshot["body"] = body

        # Keep caller-level intent visible when available.
        if "json" in kwargs:
            request_snapshot["json"] = kwargs["json"]
        if "params" in kwargs:
            request_snapshot["params"] = kwargs["params"]

        request_snapshot["curl"] = self._build_curl_command(request_snapshot)

        return request_snapshot

    @staticmethod
    def _build_curl_command(request_snapshot: dict[str, Any]) -> str:
        def sq(value: str) -> str:
            return "'" + value.replace("'", "'\"'\"'") + "'"

        method = str(request_snapshot.get("method") or "GET")
        url = str(request_snapshot.get("url") or "")
        headers = request_snapshot.get("headers") or {}

        curl_parts: list[str] = [f"curl -X {sq(method)}", sq(url)]

        accept_value = headers.get("Accept") or headers.get("accept")
        if accept_value:
            curl_parts.append(f"-H {sq(f'accept: {accept_value}')}")

        content_type_value = headers.get("Content-Type") or headers.get("content-type")
        if content_type_value:
            curl_parts.append(f"-H {sq(f'Content-Type: {content_type_value}')}")

        if "json" in request_snapshot:
            payload = json.dumps(request_snapshot["json"], separators=(",", ":"), ensure_ascii=False)
            curl_parts.append(f"-d {sq(payload)}")
        elif "body" in request_snapshot:
            curl_parts.append(f"-d {sq(str(request_snapshot['body']))}")

        separator = " \\\n" + "  "
        return separator.join(curl_parts)

    def get_last_api_request(self) -> dict[str, Any]:
        return self._last_api_request or {}

    def execute_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Execute a request to the Netskope API.
        """
        url = self.get_api_url(endpoint)
        request_kwargs = dict(kwargs)
        extra_headers = kwargs.pop("headers", {})
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            **extra_headers,
        }

        response = requests.request(method, url, headers=headers, **kwargs)
        self._last_api_request = self._serialize_request(response.request, request_kwargs)
        self._handle_response_error(response)

        return response.json() if response.content else {}
