from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from .action_base import GraphAPIException, MicrosoftGraphActionBase


class SearchMessagesArguments(BaseModel):
    """Represent validated inputs for the search messages action."""

    model_config = ConfigDict(extra="forbid")

    user: str
    email_message_id: str | None = None
    email_local_id: str | None = None
    max_messages_to_return: int = Field(default=10, ge=1, le=100)
    return_most_recent_first: bool = False


class SearchMessagesAction(MicrosoftGraphActionBase):
    """Execute message searches by internet message ID and/or network message ID."""

    NETWORK_MESSAGE_ID_EXTENDED_PROPERTY = "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId"
    FALLBACK_PAGE_SIZE = 50
    FALLBACK_MAX_MESSAGES_SCANNED = 1000

    @staticmethod
    def _escape_odata_literal(value: str) -> str:
        """Escape single quotes for safe OData string literal usage."""

        return value.replace("'", "''")

    @staticmethod
    def _extract_network_message_id(message: dict[str, Any]) -> str | None:
        """Extract the NetworkMessageId from Graph extended properties."""

        for prop in message.get("singleValueExtendedProperties", []):
            if prop.get("id") == SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY:
                value = prop.get("value")
                return value if isinstance(value, str) else None
        return None

    def _search_messages_fallback(
        self,
        user_id_or_principal_name: str,
        max_messages_to_return: int,
        return_most_recent_first: bool,
        network_message_id: str | None = None,
        internet_message_id: str | None = None,
    ) -> Any:
        """Run paginated client-side filtering by optional network/internet message IDs."""

        escaped_property = self._escape_odata_literal(self.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY)
        initial_params: dict[str, Any] = {
            "$top": max(max_messages_to_return, self.FALLBACK_PAGE_SIZE),
            "$select": "id,internetMessageId,subject,receivedDateTime,from,toRecipients",
        }

        if network_message_id:
            initial_params["$expand"] = "singleValueExtendedProperties(" f"$filter=id eq '{escaped_property}'" ")"

        if return_most_recent_first:
            initial_params["$orderby"] = "receivedDateTime desc"

        next_url = f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages"
        params: dict[str, Any] | None = initial_params
        matched_messages: list[dict[str, Any]] = []
        scanned_messages = 0

        while (
            next_url
            and len(matched_messages) < max_messages_to_return
            and scanned_messages < self.FALLBACK_MAX_MESSAGES_SCANNED
        ):
            response = self.client.get(next_url, params=params, timeout=60)
            self.handle_response(response)

            payload = response.json()
            messages: list[dict[str, Any]] = payload.get("value", [])
            scanned_messages += len(messages)

            matched_messages.extend(
                message
                for message in messages
                if (network_message_id is None or self._extract_network_message_id(message) == network_message_id)
                and (internet_message_id is None or message.get("internetMessageId") == internet_message_id)
            )

            next_url = payload.get("@odata.nextLink")
            params = None

        self.log(
            message=(
                "Completed search fallback with client-side filtering "
                f"user={user_id_or_principal_name!r} "
                f"scanned_messages={scanned_messages!r} "
                f"matched_messages={len(matched_messages)!r} "
                f"has_more={bool(next_url)!r}"
            ),
            level="debug",
        )

        return {
            "value": matched_messages[:max_messages_to_return],
            "@odata.nextLink": next_url,
        }

    def run(self, arguments: Any) -> Any:
        """Execute the search messages action and return normalized results."""

        validated_arguments = SearchMessagesArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        internet_message_id = validated_arguments.email_message_id
        network_message_id = validated_arguments.email_local_id
        max_messages_to_return = validated_arguments.max_messages_to_return
        return_most_recent_first = validated_arguments.return_most_recent_first

        if not internet_message_id and not network_message_id:
            self.log(
                message=("Detected invalid search message arguments " f"user={user_id_or_principal_name!r}"),
                level="error",
            )
            raise ValueError("Either email_message_id or email_local_id must be provided")

        if internet_message_id and network_message_id:
            query_type = "combined"
            query_value = f"email_message_id={internet_message_id};email_local_id={network_message_id}"
        elif internet_message_id:
            query_type = "email_message_id"
            query_value = internet_message_id
        else:
            query_type = "email_local_id"
            query_value = network_message_id

        self.log(
            message=(
                "Start search messages action "
                f"user={user_id_or_principal_name!r} "
                f"query_type={query_type!r} "
                f"max_messages_to_return={max_messages_to_return!r} "
                f"return_most_recent_first={return_most_recent_first!r}"
            ),
            level="debug",
        )

        used_fallback = False

        filters: list[str] = []
        if return_most_recent_first:
            # Graph requires the orderby property to be in filter and before other predicates.
            filters.append("receivedDateTime ge 1900-01-01T00:00:00Z")

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
            "$top": max_messages_to_return,
            "$select": "id,internetMessageId,subject,receivedDateTime,from,toRecipients",
        }

        if return_most_recent_first:
            params["$orderby"] = "receivedDateTime desc"

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
            if "InefficientFilter" in str(exc):
                used_fallback = True
                self.log(
                    message=(
                        "Fell back to client-side filtering after inefficient Graph filter "
                        f"user={user_id_or_principal_name!r} "
                        f"max_messages_to_return={max_messages_to_return!r}"
                    ),
                    level="warning",
                )
                payload = self._search_messages_fallback(
                    user_id_or_principal_name,
                    max_messages_to_return,
                    return_most_recent_first,
                    network_message_id,
                    internet_message_id,
                )
            else:
                raise

        if network_message_id and not payload.get("value") and not used_fallback:
            used_fallback = True
            self.log(
                message=(
                    "Fell back to client-side filtering after empty Graph results "
                    f"user={user_id_or_principal_name!r} "
                    f"max_messages_to_return={max_messages_to_return!r}"
                ),
                level="warning",
            )
            payload = self._search_messages_fallback(
                user_id_or_principal_name,
                max_messages_to_return,
                return_most_recent_first,
                network_message_id,
                internet_message_id,
            )

        messages = payload.get("value", [])
        normalized_messages = cast(list[dict[str, Any]], self._snake_case_keys(messages))
        for raw_message, message in zip(messages, normalized_messages):
            raw_message_id = message.pop("id", None)
            if isinstance(raw_message_id, str):
                message["message_id"] = raw_message_id

            network_id = self._extract_network_message_id(raw_message)
            if network_id is not None:
                message["network_message_id"] = network_id

        has_more = bool(payload.get("@odata.nextLink"))
        total_results = len(normalized_messages)
        message_ids = [
            message["message_id"] for message in normalized_messages if isinstance(message.get("message_id"), str)
        ]

        if not normalized_messages:
            self.log(
                message=(
                    "Completed search messages action "
                    f"user={user_id_or_principal_name!r} "
                    f"total_results={0!r} "
                    f"returned_count={0!r} "
                    f"has_more={has_more!r} "
                    f"used_fallback={used_fallback!r}"
                ),
                level="debug",
            )
            return {
                "user": user_id_or_principal_name,
                "query_type": query_type,
                "query_value": query_value,
                "message_ids": [],
                "messages": [],
                "total_results": 0,
                "returned_count": 0,
                "has_more": has_more,
            }

        self.log(
            message=(
                "Completed search messages action "
                f"user={user_id_or_principal_name!r} "
                f"total_results={total_results!r} "
                f"returned_count={total_results!r} "
                f"has_more={has_more!r} "
                f"used_fallback={used_fallback!r}"
            ),
            level="debug",
        )
        return {
            "user": user_id_or_principal_name,
            "query_type": query_type,
            "query_value": query_value,
            "message_ids": message_ids,
            "messages": normalized_messages,
            "total_results": total_results,
            "returned_count": total_results,
            "has_more": has_more,
        }
