from typing import Any

from .action_base import MicrosoftGraphActionBase


class ResolveMessageAction(MicrosoftGraphActionBase):
    NETWORK_MESSAGE_ID_EXTENDED_PROPERTY = "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId"

    @staticmethod
    def _escape_odata_literal(value: str) -> str:
        return value.replace("'", "''")

    def run(self, arguments: Any) -> Any:
        user_id_or_principal_name = arguments["user"]
        email_message_id: str | None = arguments.get("email_message_id")
        email_local_id: str | None = arguments.get("email_local_id")
        top: int = arguments.get("top", 10)
        item_index: int = arguments.get("item_index", 0)
        most_recent: bool = arguments.get("most_recent", False)

        if not email_message_id and not email_local_id:
            raise ValueError("Either email_message_id or email_local_id must be provided")

        if item_index < 0:
            raise ValueError("item_index must be greater than or equal to 0")

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
            params["$expand"] = (
                "singleValueExtendedProperties("
                f"$filter=id eq '{escaped_property}'"
                ")"
            )

        response = self.client.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages",
            params=params,
            timeout=60,
        )
        self.handle_response(response)

        payload = response.json()
        messages: list[dict[str, Any]] = payload.get("value", [])

        if not messages:
            raise ValueError("No message found for the provided identifier(s)")

        if item_index >= len(messages):
            raise ValueError(f"item_index {item_index} is out of range for {len(messages)} result(s)")

        selected_message = messages[item_index]

        return {
            "graph_message_id": selected_message.get("id"),
            "selected_index": item_index,
            "total_results": len(messages),
            "selected_message": selected_message,
            "messages": messages,
        }
