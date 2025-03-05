import time
from abc import ABC
from datetime import datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Any, Generator, Sequence, Tuple
from urllib.parse import urljoin

import requests
from dateutil import parser
from dateutil.parser import ParserError, isoparse
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from . import VadeSecureModule
from .client import ApiClient
from .models import VadeSecureTriggerConfiguration


class APIException(Exception):

    def __init__(self, code: int, reason: str, content: str):
        super().__init__(reason)
        self.code = code
        self.content = content


class EventType(Enum):
    EMAILS = "emails"
    REMEDIATIONS_AUTO = "remediations/auto"
    REMEDIATIONS_MANUAL = "remediations/manual"


class M365Mixin(Trigger, ABC):
    module: VadeSecureModule
    configuration: VadeSecureTriggerConfiguration

    def __init__(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @cached_property
    def client(self) -> ApiClient:
        try:
            return ApiClient(
                auth_url=self.module.configuration.oauth2_authorization_url,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )

        except requests.exceptions.HTTPError as error:
            response = error.response
            level = "critical" if response.status_code in [401, 403] else "error"
            self.log(
                f"OAuth2 server responded {response.status_code} - {response.reason}",
                level=level,
            )
            raise error

        except TimeoutError as error:
            self.log(message="Failed to authorize due to timeout", level="error")
            raise error

    def get_event_type_context(self, event_type: EventType) -> Tuple[datetime, str | None]:
        """
        Get last event date and id.

        Returns:
            Tuple[datetime, str | None]:
        """
        # no need to fetch events from more than 1 hour
        # it happens when last received event was more than one hour ago
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        with self.context as cache:
            event_type_context = cache.get(event_type.value)
            if not event_type_context:
                event_type_context = {}

            last_message_date_str = event_type_context.get("last_message_date")
            last_message_id = event_type_context.get("last_message_id")

            if last_message_date_str is None:
                return one_hour_ago, last_message_id

            last_event_date = isoparse(last_message_date_str)

            if last_event_date < one_hour_ago:
                return one_hour_ago, last_message_id

            return last_event_date, last_message_id

    def update_event_type_context(
        self, last_message_date: datetime, last_message_id: str | None, event_type: EventType
    ) -> None:
        """
        Set last event date.

        Args:
            last_message_date: datetime
            last_message_id: str
            event_type: EventType
        """
        with self.context as cache:
            cache[event_type.value] = {"last_message_date": last_message_date.isoformat()}

            if last_message_id:
                cache[event_type.value]["last_message_id"] = last_message_id

    def _get_last_message_date(self, events: list[Any]) -> datetime:
        for event in reversed(events):
            try:
                # Make the date timezone naive to support comparison with datetime.utcnow()
                return parser.parse(event["date"]).replace(tzinfo=None)
            except (ParserError, KeyError):
                self.log(message="Failed to parse event date", level="error")
        raise ValueError("No event had a valid date")

    def _fetch_next_events(
        self, last_message_id: str | None, last_message_date: datetime, event_type: EventType
    ) -> list[dict[str, Any]]:
        """
        Returns the next page of events produced by M365
        """
        payload_json = {
            "limit": self.configuration.pagination_limit,
            "sort": [{"date": "asc"}, "id"],
            "search_after": [last_message_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), last_message_id or ""],
        }

        url = urljoin(
            self.module.configuration.api_host.rstrip("/"),
            f"api/v1/tenants/{self.configuration.tenant_id}/logs/{event_type.value}/search",
        )

        response = self.client.post(url=url, json=payload_json, timeout=60)

        if not response.ok:
            if response.status_code in [401, 500]:
                raise APIException(response.status_code, response.reason, response.text)
            else:
                # Exit trigger if we can't authenticate against the server
                level = "critical" if response.status_code in [403] else "error"
                self.log(
                    message=(
                        f"Request on M365 API to fetch events of tenant {self.configuration.tenant_id} "
                        f"failed with status {response.status_code} - {response.reason}"
                    ),
                    level=level,
                )

                return []
        else:
            result: list[dict[str, Any]] = (
                response.json()["result"]["messages"]
                if event_type == EventType.EMAILS
                else response.json()["result"]["campaigns"]
            )

            return result

    def handle_api_exception(self, error: APIException) -> None:
        message = f"Unexpected API error {error.code} - {str(error)} - {error.content}"
        if error.code == 401:
            message = "The VadeCloud API raised an authentication issue. Please check our credentials"
        elif error.code == 500:
            message = (
                "The VadeCloud API raised an internal error. Please contact the Vade support if the issue persists"
            )
        self.log(level="error", message=message)
        time.sleep(self.configuration.frequency)

    def run(self) -> None:  # pragma: no cover
        """Run the trigger."""
        while True:
            try:
                self._fetch_events()
            except APIException as ex:
                self.handle_api_exception(ex)
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise
