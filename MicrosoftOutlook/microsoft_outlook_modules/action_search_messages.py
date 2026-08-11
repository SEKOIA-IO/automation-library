from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase


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

        response = self.client.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages",
            params=params,
            timeout=60,
        )
        self.handle_response(response)

        return response.json()
