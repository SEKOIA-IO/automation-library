import re
from abc import ABC
from functools import cached_property, wraps
from typing import Any

from requests import Response
from sekoia_automation.action import Action

from . import MicrosoftOutlookModule
from .client import ApiClient
from .errors import ActionInputError, GraphAPIError, describe_error


class MicrosoftGraphActionBase(Action, ABC):
    """Provide shared utilities for Microsoft Graph actions."""

    module: MicrosoftOutlookModule

    may_modify_data = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        validated_run = self.run

        @wraps(validated_run)
        def guarded_run(*run_args, **run_kwargs):
            self.error("")
            try:
                result = validated_run(*run_args, **run_kwargs)
                if isinstance(result, dict):
                    result.setdefault("outcome", "failed" if self.error_message else "succeeded")
                return result
            except Exception as exc:
                detail = describe_error(exc, may_modify=self.may_modify_data)
                self.error(detail["message"])
                return {"outcome": "unknown" if detail["outcome_unknown"] else "failed", "error_details": [detail]}

        self.run = guarded_run

    def report_item_errors(self, result: dict, details: list[dict], outcome: str) -> dict:
        result["outcome"] = outcome
        result["error_details"] = details
        if details:
            self.error(f"Action outcome: {outcome}. {details[0]['message']}")
        return result

    _CAMEL_BOUNDARY_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")

    @staticmethod
    def _read_client_secret(secret_value: object) -> str:
        """Return a usable client secret string from supported secret types."""
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
        """Convert a camelCase or PascalCase key to snake_case."""

        return cls._CAMEL_BOUNDARY_PATTERN.sub("_", key).lower()

    @classmethod
    def _snake_case_keys(cls, value: Any) -> Any:
        """Recursively convert dictionary keys to snake_case."""

        if isinstance(value, list):
            return [cls._snake_case_keys(item) for item in value]

        if isinstance(value, dict):
            return {cls._to_snake_case(k): cls._snake_case_keys(v) for k, v in value.items()}

        return value

    @staticmethod
    def _resolve_message_id(message_id_or_item: Any) -> str:
        """Extract a message ID from a string or message-like dictionary."""

        if isinstance(message_id_or_item, str) and message_id_or_item.strip():
            return message_id_or_item.strip()

        # Foreach items are message objects; support direct chaining without manual field extraction.
        if isinstance(message_id_or_item, dict):
            nested_message_id = message_id_or_item.get("message_id")
            if isinstance(nested_message_id, str) and nested_message_id.strip():
                return nested_message_id.strip()

        raise ActionInputError("message_id must be a string or a message object containing a string message_id")

    @staticmethod
    def _generate_recipient(email: str) -> dict[str, Any]:
        """Build a Microsoft Graph recipient payload from an email address."""

        return {"emailAddress": {"name": email, "address": email}}

    @staticmethod
    def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of a dictionary without keys mapped to None."""

        return {k: v for k, v in values.items() if v is not None}

    @cached_property
    def client(self) -> ApiClient:
        """Create and cache an authenticated Microsoft Graph API client."""

        return ApiClient(
            tenant_id=self.module.configuration.tenant_id,
            app_id=self.module.configuration.client_id,
            app_secret=self._read_client_secret(self.module.configuration.client_secret),
        )

    def handle_response(self, response: Response) -> None:
        """Preserve the search fallback while keeping raw error bodies out of logs."""
        if response.ok:
            return
        if response.status_code == 400:
            code = "BadRequest"
            try:
                if response.json().get("error", {}).get("code") == "InefficientFilter":
                    code = "InefficientFilter"
            except ValueError:
                pass
            except AttributeError:
                pass
            raise GraphAPIError(code, response=response)
        response.raise_for_status()
