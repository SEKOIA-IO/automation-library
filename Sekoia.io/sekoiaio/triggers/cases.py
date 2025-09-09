import uuid
from posixpath import join as urljoin

import orjson
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

from sekoiaio.logging import get_logger
from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger


logger = get_logger(__name__)


class SecurityCasesTrigger(_SEKOIANotificationBaseTrigger):
    # List of cases types we can handle.
    HANDLED_EVENT_SUB_TYPES = [
        ("case", "created"),
        ("case", "updated"),
        ("case", "alerts-updated"),
    ]

    def _filter_by_mode(self, case) -> bool:
        mode_filter = self.configuration.get("mode_filter")
        if mode_filter and case.get("manual") != (mode_filter == "manual"):
            return False

        return True

    def _filter_by_priority(self, case) -> bool:
        priority_uuids_filter = self.configuration.get("priority_uuids_filter")
        if priority_uuids_filter and case.get("custom_priority_uuid") not in priority_uuids_filter:
            return False

        return True

    def _filter_by_assignees(self, case) -> bool:
        assignees_filter = self.configuration.get("assignees_filter")
        if assignees_filter:
            if not any(assignee.get("avatar_uuid") in assignees_filter for assignee in case.get("subscribers", [])):
                return False

        return True

    def _filter_by_uuids(self, case) -> bool:
        case_uuids_filter = self.configuration.get("case_uuids_filter")
        if (
            case_uuids_filter
            and case.get("uuid") not in case_uuids_filter
            and case.get("short_id") not in case_uuids_filter
        ):
            return False

        return True

    @retry(
        reraise=True,
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(10),
    )
    def _retrieve_case_from_caseapi(self, case_uuid):
        api_url = urljoin(self.module.configuration["base_url"], f"api/v1/sic/cases/{case_uuid}")
        api_url = api_url.replace("/api/api", "/api")  # In case base_url ends with /api

        api_key = self.module.configuration["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()}

        response = requests.get(
            api_url,
            headers=headers,
        )

        if not response.ok:
            try:
                content = response.json()
            except Exception:
                content = response.text
            self.log(
                "Error while fetching case from Case API",
                level="error",
                status_code=response.status_code,
                content=content,
            )

        # raise an exception if the http request failed
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exp:
            self.log(
                "Failed to parse JSON response from Case API",
                level="error",
                content=response.text,
            )
            raise exp


class CaseCreatedTrigger(SecurityCasesTrigger):
    HANDLED_EVENT_SUB_TYPES = [("case", "created")]

    def handle_event(self, message):
        """Handle case created messages with filters."""
        case_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore cases “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            logger.debug(
                "Discard no case created notification",
                received_event_type=event_type,
                receive_event_action=event_action,
            )
            return

        # Is the notification in a format we can understand?
        case_uuid: str = case_attrs.get("uuid", "")
        if not case_uuid:
            logger.debug("The notification does not contain a case UUID", case_attrs=case_attrs)
            return

        try:
            case = self._retrieve_case_from_caseapi(case_uuid)

        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch case from case API")
            return

        filter_case = [
            self._filter_by_mode(case),
            self._filter_by_priority(case),
            self._filter_by_assignees(case),
        ]

        if not all(filter for filter in filter_case):
            logger.debug("Case does not match the filters", case_uuid=case_uuid, case_attrs=case_attrs)
            return

        case_short_id = case_attrs.get("short_id")
        event = {
            "uuid": case_uuid,
            "short_id": case_short_id,
            "created_at": case_attrs.get("created_at"),
            "created_by": case.get("created_by"),
            "mode": "manual" if case_attrs.get("manual") else "automatic",
            "title": case_attrs.get("title"),
            "description": case.get("description"),
            "community_uuid": case.get("community_uuid"),
            "assignees": case.get("assignees", []),
            "priority_uuid": case_attrs.get("custom_priority_uuid"),
            "status_uuid": case.get("status_uuid"),
            "tags": case.get("tags", []),
        }

        self.send_event(
            event_name=f"Sekoia.io case: {case_short_id}",
            event=event,
        )


class CaseUpdatedTrigger(SecurityCasesTrigger):
    HANDLED_EVENT_SUB_TYPES = [("case", "updated")]

    def handle_event(self, message):
        """Handle case updated messages with filters."""
        case_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore cases “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            logger.debug(
                "Discard no case updated notification",
                received_event_type=event_type,
                receive_event_action=event_action,
            )
            return

        # Is the notification in a format we can understand?
        case_uuid: str = case_attrs.get("uuid", "")
        if not case_uuid:
            logger.debug("The notification does not contain a case UUID", case_attrs=case_attrs)
            return

        try:
            case = self._retrieve_case_from_caseapi(case_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch case from case API")
            return

        filter_case = [
            self._filter_by_mode(case),
            self._filter_by_priority(case),
            self._filter_by_assignees(case),
            self._filter_by_uuids(case),
        ]

        if not all(filter_case):
            logger.debug("Case does not match the filters", case_uuid=case_uuid, case_attrs=case_attrs)
            return

        case_short_id = case.get("short_id")
        event = {
            "uuid": case_uuid,
            "short_id": case_short_id,
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
            "updated_by": case.get("updated_by"),
        }

        for key in [
            "title",
            "description",
            "community_uuid",
            "assignees",
            "tags",
            "custom_priority_uuid",
            "status_uuid",
            "verdict_uuid",
        ]:
            if key in case_attrs.get("updated", {}).keys():
                event[key] = case_attrs.get("updated", {}).get(key)

        self.send_event(
            event_name=f"Sekoia.io case: {case_short_id}",
            event=event,
        )


class CaseAlertsUpdatedTrigger(SecurityCasesTrigger):
    HANDLED_EVENT_SUB_TYPES = [("case", "alerts-updated")]

    def handle_event(self, message):
        """Handle case alerts updated messages with filters."""
        case_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore cases “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            logger.debug(
                "Discard no case alert-updated notification",
                received_event_type=event_type,
                receive_event_action=event_action,
            )
            return

        # Is the notification in a format we can understand?
        case_uuid: str = case_attrs.get("uuid", "")
        if not case_uuid:
            logger.debug("The notification does not contain a case UUID", case_attrs=case_attrs)
            return

        try:
            case = self._retrieve_case_from_caseapi(case_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch case from case API")
            return

        filter_case = [
            self._filter_by_mode(case),
            self._filter_by_priority(case),
            self._filter_by_assignees(case),
            self._filter_by_uuids(case),
        ]

        if not all(filter for filter in filter_case):
            logger.debug("Case does not match the filters", case_uuid=case_uuid, case_attrs=case_attrs)
            return

        case_short_id = case.get("short_id")
        event = {
            "uuid": case_uuid,
            "short_id": case_short_id,
            "added_alerts": case_attrs.get("updated", {}).get("added_alerts_uuid", []),
            "deleted_alerts": case_attrs.get("updated", {}).get("deleted_alerts_uuid", []),
        }

        self.send_event(
            event_name=f"Sekoia.io case: {case_short_id}",
            event=event,
        )
