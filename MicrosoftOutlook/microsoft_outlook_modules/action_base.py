import re
from abc import ABC
from functools import cached_property
from typing import Any

from requests import Response
from sekoia_automation.action import Action

from . import MicrosoftOutlookModule
from .client import ApiClient


class GraphAPIException(Exception):
    pass


class MicrosoftGraphActionBase(Action, ABC):
    module: MicrosoftOutlookModule

    _CAMEL_BOUNDARY_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")

    @staticmethod
    def _read_client_secret(secret_value: object) -> str:
        """Accept either a Pydantic SecretStr-like value or a raw string."""
        if isinstance(secret_value, str):
            return secret_value

        getter = getattr(secret_value, "get_secret_value", None)
        if callable(getter):
            resolved_value = getter()
            if isinstance(resolved_value, str):
                return resolved_value

        raise TypeError("Invalid client_secret type: expected string or SecretStr-like value")

    @classmethod
    def _to_snake_case(cls, key: str) -> str:
        return cls._CAMEL_BOUNDARY_PATTERN.sub("_", key).lower()

    @classmethod
    def _snake_case_keys(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._snake_case_keys(item) for item in value]

        if isinstance(value, dict):
            return {cls._to_snake_case(k): cls._snake_case_keys(v) for k, v in value.items()}

        return value

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            tenant_id=self.module.configuration.tenant_id,
            app_id=self.module.configuration.client_id,
            app_secret=self._read_client_secret(self.module.configuration.client_secret),
        )

    def handle_response(self, response: Response) -> None:
        if not response.ok:
            message = f"Request to Microsoft Graph API failed with status {response.status_code} - {response.reason}"
            if response.status_code == 400:
                message = response.text
                self.log(message=message, level="error")
                raise GraphAPIException(message)

            self.log(message=message, level="error")
            response.raise_for_status()
