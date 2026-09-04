from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from .action_base import GraphAPIException, MicrosoftGraphActionBase


class ResolveMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    email_message_id: str | None = None
    email_local_id: str | None = None
    top: int = Field(default=10, ge=1, le=100)
    item_index: int = Field(default=0, ge=0)
    most_recent: bool = False


class ResolveMessageAction(MicrosoftGraphActionBase):
    NETWORK_MESSAGE_ID_EXTENDED_PROPERTY = "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId"

    @staticmethod
    def _escape_odata_literal(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _extract_network_message_id(message: dict[str, Any]) -> str | None:
        for prop in message.get("singleValueExtendedProperties", []):
            if prop.get("id") == ResolveMessageAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY:
                value = prop.get("value")
                return value if isinstance(value, str) else None
        return None

    def _resolve_by_network_message_id_fallback(
        self, user_id_or_principal_name: str, email_local_id: str, top: int
    ) -> Any:
        escaped_property = self._escape_odata_literal(self.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY)
        params: dict[str, Any] = {
            "$top": top,
            "$select": "id,internetMessageId,subject,receivedDateTime,from,toRecipients",
            "$expand": "singleValueExtendedProperties(" f"$filter=id eq '{escaped_property}'" ")",
            "$orderby": "receivedDateTime desc",
        }

        response = self.client.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages",
            params=params,
            timeout=60,
        )
        self.handle_response(response)

        payload = response.json()
        messages: list[dict[str, Any]] = payload.get("value", [])
        payload["value"] = [
            message for message in messages if self._extract_network_message_id(message) == email_local_id
        ]
        return payload

    def run(self, arguments: Any) -> Any:
        validated_arguments = ResolveMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        email_message_id = validated_arguments.email_message_id
        email_local_id = validated_arguments.email_local_id
        top = validated_arguments.top
        item_index = validated_arguments.item_index
        most_recent = validated_arguments.most_recent

        if not email_message_id and not email_local_id:
            raise ValueError("Either email_message_id or email_local_id must be provided")

        filters: list[str] = []
        if email_message_id:
            escaped_email_message_id = self._escape_odata_literal(email_message_id)
            filters.append(f"internetMessageId eq '{escaped_email_message_id}'")

        if email_local_id:
            escaped_email_local_id = self._escape_odata_literal(email_local_id)
            escaped_property = self._escape_odata_literal(self.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY)
            filters.append(
                "singleValueExtendedProperties/any(ep:"
                f"ep/id eq '{escaped_property}' and ep/value eq '{escaped_email_local_id}')"
            )

        params: dict[str, Any] = {
            "$filter": " and ".join(filters),
            "$top": top,
            "$select": "id,internetMessageId,subject,receivedDateTime,from,toRecipients",
        }

        if most_recent:
            params["$orderby"] = "receivedDateTime desc"

        if email_local_id:
            escaped_property = self._escape_odata_literal(self.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY)
            params["$expand"] = "singleValueExtendedProperties(" f"$filter=id eq '{escaped_property}'" ")"

        try:
            response = self.client.get(
                f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages",
                params=params,
                timeout=60,
            )
            self.handle_response(response)
            payload = response.json()
        except GraphAPIException as exc:
            if email_local_id and "InefficientFilter" in str(exc):
                self.log(message="Fallback to client-side NetworkMessageId filtering", level="warning")
                payload = self._resolve_by_network_message_id_fallback(user_id_or_principal_name, email_local_id, top)
            else:
                raise

        if email_local_id and not payload.get("value"):
            self.log(message="No results with NetworkMessageId filter, retrying with fallback", level="warning")
            payload = self._resolve_by_network_message_id_fallback(user_id_or_principal_name, email_local_id, top)

        messages: list[dict[str, Any]] = payload.get("value", [])

        if not messages:
            raise ValueError("No message found for the provided identifier(s)")

        if item_index >= len(messages):
            raise ValueError(f"item_index {item_index} is out of range for {len(messages)} result(s)")

        selected_message = messages[item_index]
        resolved_message_id = selected_message.get("id") if isinstance(selected_message.get("id"), str) else None
        if resolved_message_id is None:
            raise ValueError("Unable to resolve a valid string message_id from selected message")

        normalized_selected_message = cast(dict[str, Any], self._snake_case_keys(selected_message))
        normalized_selected_message.pop("id", None)
        normalized_selected_message["message_id"] = resolved_message_id

        normalized_messages = cast(list[dict[str, Any]], self._snake_case_keys(messages))
        for message in normalized_messages:
            raw_message_id = message.pop("id", None)
            if isinstance(raw_message_id, str):
                message["message_id"] = raw_message_id

        return {
            "message_id": resolved_message_id,
            "selected_index": item_index,
            "total_results": len(messages),
            "selected_message": normalized_selected_message,
            "messages": normalized_messages,
        }
