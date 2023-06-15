import uuid
from posixpath import join as urljoin

import orjson
import requests

from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger


class SecurityAlertsTrigger(_SEKOIANotificationBaseTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [
        "alert-created",
        "alert-updated",
        "alert-status-changed",
        "alert-comment-created",
    ]

    def handle_alert(self, message):
        """Handle alert messages.

        Only a few event are considered (`alert-created`,
        `alert-updated`, `alert-status-changed`,
        `alert-comment-created`). If a valid evnet is handled, then
        enrich event from `sicalertapi` to retrieve its status, its
        short id, etc. Finally, send message to the Symphony workflow.

        """
        alert_attrs = message.get("attributes", {})
        alert_event: str | None = alert_attrs.get("event")
        alert_uuid: str | None = alert_attrs.get("alert_uuid")

        # Is the notification in a format we can understand?
        if not (alert_event and alert_uuid):
            return

        # Ignore alert “sub event” types that we can’t (yet) handle.
        if alert_event not in self.HANDLED_EVENT_SUB_TYPES:
            return

        alert = self._retrieve_alert_from_alertapi(alert_uuid)

        if rule_filter := self.configuration.get("rule_filter"):
            if alert["rule"]["name"] != rule_filter and alert["rule"]["uuid"] != rule_filter:
                return

        work_dir = self._data_path.joinpath("sekoiaio_securityalerts").joinpath(str(uuid.uuid4()))
        alert_path = work_dir.joinpath("alert.json")
        work_dir.mkdir(parents=True, exist_ok=True)

        with alert_path.open("w") as fp:
            fp.write(orjson.dumps(alert).decode("utf-8"))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(alert_path.relative_to(work_dir))

        alert_short_id = alert.get("short_id")
        event = {
            "file_path": file_path,
            "event_type": alert_event,
            "alert_uuid": alert_uuid,
            "short_id": alert_short_id,
            "status": {
                "name": alert.get("status", {}).get("name"),
                "uuid": alert.get("status", {}).get("uuid"),
            },
            "created_at": alert.get("created_at"),
            "urgency": alert.get("urgency", {}).get("current_value"),
            "entity": alert.get("entity", {}),
            "alert_type": alert.get("alert_type", {}),
            "rule": {"name": alert["rule"]["name"], "uuid": alert["rule"]["uuid"]},
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
        }

        self.send_event(
            event_name=f"SEKOIA.IO Alert: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    def _retrieve_alert_from_alertapi(self, alert_uuid):
        api_url = urljoin(self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}")

        api_key = self.module.configuration["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()}

        response = requests.get(
            api_url,
            headers=headers,
            params={
                "stix": False,
                "comments": False,
                "countermeasures": False,
                "history": False,
            },
        )

        # raise an exception if the http request failed
        response.raise_for_status()

        return response.json()


class AlertCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = ["alert-created"]


class AlertUpdatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = ["alert-updated"]


class AlertStatusChangedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = ["alert-status-changed"]


class AlertCommentCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = ["alert-comment-created"]
