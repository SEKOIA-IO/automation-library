from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from .action_base import GraphAPIException, MicrosoftGraphActionBase


class SearchMessagesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    email_message_id: str | None = None
    email_local_id: str | None = None
    top: int = Field(default=10, ge=1, le=100)


class SearchMessagesAction(MicrosoftGraphActionBase):
    NETWORK_MESSAGE_ID_EXTENDED_PROPERTY = "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId"

    @staticmethod
    def _escape_odata_literal(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _extract_network_message_id(message: dict[str, Any]) -> str | None:
        for prop in message.get("singleValueExtendedProperties", []):
            if prop.get("id") == SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY:
                value = prop.get("value")
                return value if isinstance(value, str) else None
        return None

    def _search_by_network_message_id_fallback(
        self, user_id_or_principal_name: str, network_message_id: str, top: int
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
        filtered_messages = [
            message for message in messages if self._extract_network_message_id(message) == network_message_id
        ]

        payload["value"] = filtered_messages
        return payload

    def run(self, arguments: Any) -> Any:
        validated_arguments = SearchMessagesArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        internet_message_id = validated_arguments.email_message_id
        network_message_id = validated_arguments.email_local_id
        top = validated_arguments.top

        if not internet_message_id and not network_message_id:
            raise ValueError("Either email_message_id or email_local_id must be provided")

        filters: list[str] = []
        if internet_message_id:
            escaped_internet_message_id = self._escape_odata_literal(internet_message_id)
            filters.append(f"internetMessageId eq '{escaped_internet_message_id}'")

        if network_message_id:
            escaped_network_message_id = self._escape_odata_literal(network_message_id)
            escaped_property = self._escape_odata_literal(self.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY)
            filters.append(
                "singleValueExtendedProperties/any(ep:"
                f"ep/id eq '{escaped_property}' and ep/value eq '{escaped_network_message_id}')"
            )

        params: dict[str, Any] = {
            "$filter": " and ".join(filters),
            "$top": top,
            "$select": "id,internetMessageId,subject,receivedDateTime,from,toRecipients",
        }

        if network_message_id:
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
            if network_message_id and "InefficientFilter" in str(exc):
                self.log(message="Fallback to client-side NetworkMessageId filtering", level="warning")
                payload = self._search_by_network_message_id_fallback(
                    user_id_or_principal_name, network_message_id, top
                )
            else:
                raise

        if network_message_id and not payload.get("value"):
            self.log(message="No results with NetworkMessageId filter, retrying with fallback", level="warning")
            payload = self._search_by_network_message_id_fallback(user_id_or_principal_name, network_message_id, top)

        messages = payload.get("value", [])
        normalized_messages = cast(list[dict[str, Any]], self._snake_case_keys(messages))
        for message in normalized_messages:
            raw_message_id = message.pop("id", None)
            if isinstance(raw_message_id, str):
                message["message_id"] = raw_message_id

        return {"messages": normalized_messages}
