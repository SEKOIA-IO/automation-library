from collections.abc import Generator
from datetime import datetime
from enum import StrEnum
from typing import Any
from functools import cached_property
from posixpath import join as urljoin

from pydantic.v1 import Field
import requests

from hornetsecurity_modules.connector_base import (
    BaseConnector,
    BaseConnectorConfiguration,
)
from hornetsecurity_modules.errors import (
    FailedEmailHeaderFetchError,
    InvalidObjectIdError,
    UnknownObjectIdError,
)
from hornetsecurity_modules.helpers import (
    ApiError,
    utc_zulu_format,
    range_offset_limit,
    has_more_emails,
)
from hornetsecurity_modules.logging import get_logger


logger = get_logger()


DIRECTIONS = {"Both": None, "Incoming": 1, "Outgoing": 2}


class Direction(StrEnum):
    """
    Enum representing the direction of emails.
    """

    BOTH = "Both"
    INCOMING = "Incoming"
    OUTGOING = "Outgoing"

    def to_id(self) -> int | None:
        """
        Convert the direction to its corresponding ID.
        """
        return DIRECTIONS.get(self.value, None)


class SMPEventsConnectorConfiguration(BaseConnectorConfiguration):
    scope: str = Field(..., description="Domain name, email address or object ID to monitor")
    direction: Direction = Field(..., description="Direction of the emails to fetch (Both, Incoming or Outgoing)")
    include_header: bool = Field(False, description="Include email header in the response (default: False)")


class SMPEventsConnector(BaseConnector):
    configuration: SMPEventsConnectorConfiguration
    ID_FIELD: str = "es_mail_id"

    def handle_response(self, response: requests.Response) -> Any:
        """
        Handle the response from the API call.
        """
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"
            error = ApiError.from_response_error(response)

            logger.error(
                "Request failed",
                response_status_code=error.status_code,
                response_reason=error.reason,
                error_code=error.id,
                error_message=error.message,
                error_data=error.data,
            )

            self.log(message=str(error), level=level)

    def get_object_id_from_scope(self, scope: str) -> int:
        """
        Get the object ID from the scope, which can be a domain name, email address, or object ID.
        """
        # Check if the scope is already a digit (object ID)
        if scope.isdigit():
            return int(scope)

        # Otherwise, make a request to get the object ID
        url = urljoin(self.url, "object/")
        response = self.client.get(url, params={"name": scope})
        self.handle_response(response)

        # Raise an error if the response is not OK
        if not response.ok:
            raise UnknownObjectIdError(scope)

        # Parse the response to get the object ID
        response_data = response.json()
        object_id = response_data.get("object_id", 0)

        if isinstance(object_id, int):
            return int(object_id)
        else:
            raise InvalidObjectIdError(object_id)

    @cached_property
    def object_id(self) -> int:
        """
        Get the object ID based on the scope defined in the configuration.
        """
        return self.get_object_id_from_scope(self.configuration.scope)

    def get_email_header(self, object_id: int, es_mail_id: str) -> str:
        """
        Get the email header for a specific email ID.
        """
        url = urljoin(self.url, "emails/header/")
        response = self.client.post(
            url,
            json={"es_mail_id": es_mail_id},
            params={"object_id": object_id},
        )
        self.handle_response(response)

        # Raise an error if the response is not OK
        if not response.ok:
            raise FailedEmailHeaderFetchError(object_id, es_mail_id)

        # Parse the response to get the raw header
        response_data = response.json()
        return response_data.get("raw_header")

    def enrich_event_with_header(self, event: dict[str, Any], enrich_with_header: bool) -> dict[str, Any]:
        try:
            if enrich_with_header and "es_mail_id" in event:
                event["raw_header"] = self.get_email_header(self.object_id, event["es_mail_id"])
            else:
                event["raw_header"] = None

        except FailedEmailHeaderFetchError as e:
            logger.warning(
                "Failed to enrich event with header",
                object_id=self.object_id,
                es_mail_id=event.get("es_mail_id"),
            )
            self.log(
                level="warning",
                message=f"Failed to enrich event with header for object ID {self.object_id} and email ID {event.get('es_mail_id', 'N/A')}",
            )
        finally:
            return event

    def _fetch_events(self, from_date: datetime, to_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        """
        Fetch events from the API within the specified date range.
        """
        url = urljoin(self.url, "emails/_search/")

        # Prepare the payload for the API request
        payload: dict[str, Any] = {
            "date_from": utc_zulu_format(from_date),
            "date_to": utc_zulu_format(to_date),
        }

        # iter over the events in chunks
        for offset, limit in range_offset_limit(0, self.configuration.chunk_size):
            # Update the payload with the current offset and limit
            payload.update(
                {
                    "limit": limit,
                    "offset": offset,
                }
            )

            # If a direction is specified, add it to the payload
            if direction := self.configuration.direction.to_id():
                payload["direction"] = [direction]

            # Get the next batch of events
            logger.info(
                "Fetching events from API",
                from_date=payload["date_from"],
                to_date=payload["date_to"],
                offset=offset,
                limit=limit,
                direction=payload.get("direction"),
                object_id=self.object_id,
            )
            response = self.client.post(
                url,
                json=payload,
                params={"object_id": self.object_id},
            )

            # Handle the response
            self.handle_response(response)

            # Return if the response is not OK
            if not response.ok:
                return

            # Extract the content from the response
            try:
                content = response.json()

                # Extract emails from the content
                emails = content.get("emails", [])
                if not emails:
                    logger.info("No emails found in the response.", emails=emails)
                    self.log(
                        message="No emails found in the response.",
                        level="info",
                    )
                    return

                # Yield the emails
                yield [self.enrich_event_with_header(email, self.configuration.include_header) for email in emails]

                # Check if there are more emails to fetch
                total_found = content.get("num_found_items")
                if not has_more_emails(total_found, offset, limit):
                    logger.info("No more events to fetch.")
                    return

            except requests.exceptions.JSONDecodeError as e:
                logger.error(
                    "Failed to parse response content",
                    error=str(e),
                    response_content=response.content,
                )
                self.log(
                    message="Failed to parse response content",
                    level="error",
                )
                return
