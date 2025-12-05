import uuid
from posixpath import join as urljoin

import orjson
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger


class SecurityAlertsTrigger(_SEKOIANotificationBaseTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "created"), ("alert", "updated"), ("alert-comment", "created")]

    def handle_event(self, message):
        """Handle alert messages.

        Only a few event are considered (`alert:created`,
        `alert:updated`, `alert-comment:created`). If a valid evnet is
        handled, then enrich event from `sicalertapi` to retrieve its
        status, its short id, etc. Finally, send message to the
        Symphony workflow.

        """
        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore alert “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            return

        # Is the notification in a format we can understand?
        alert_uuid: str = alert_attrs.get("uuid", "")
        if not alert_uuid:
            return

        if not self._filter_notifications(message):
            return

        try:
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from Alert API")
            return

        if rule_filter := self.configuration.get("rule_filter"):
            if alert["rule"]["name"] != rule_filter and alert["rule"]["uuid"] != rule_filter:
                return

        if rule_names_filter := self.configuration.get("rule_names_filter"):
            if alert["rule"]["name"] not in rule_names_filter:
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
            "event_type": event_type,
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
            event_name=f"Sekoia.io Alert: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    def _filter_notifications(self, message) -> bool:
        return True

    @retry(
        reraise=True,
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(10),
    )
    def _retrieve_alert_from_alertapi(self, alert_uuid):
        api_url = urljoin(self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}")
        api_url = api_url.replace("/api/api", "/api")  # In case base_url ends with /api

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

        if not response.ok:
            try:
                content = response.json()
            except Exception:
                content = response.text
            self.log(
                "Error while fetching alert from Alert API",
                level="error",
                status_code=response.status_code,
                content=content,
            )

        # raise an exception if the http request failed
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exp:
            self.log("Failed to parse JSON response from Alert API", level="error", content=response.text)
            raise exp


class AlertCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "created")]


class AlertUpdatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "updated")]


class AlertStatusChangedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "updated")]

    def _filter_notifications(self, message) -> bool:
        if message.get("attributes", {}).get("updated", {}).get("status"):
            return True
        return False


class AlertCommentCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert-comment", "created")]

    def handle_event(self, message):
        """Handle alert messages.

        Only a few event are considered (`alert:created`,
        `alert:updated`, `alert-comment:created`). If a valid evnet is
        handled, then enrich event from `sicalertapi` to retrieve its
        status, its short id, etc. Finally, send message to the
        Symphony workflow.

        """
        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore alert “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            return

        # Is the notification in a format we can understand?
        alert_uuid: str = alert_attrs.get("alert_uuid", "")
        if not alert_uuid:
            return

        comment_uuid: str = alert_attrs.get("uuid", "")
        if not comment_uuid:
            return

        if not self._filter_notifications(message):
            return

        try:
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
            comment = self._retrieve_comment_from_alertapi(alert_uuid, comment_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from Alert API")
            return

        if rule_filter := self.configuration.get("rule_filter"):
            if alert["rule"]["name"] != rule_filter and alert["rule"]["uuid"] != rule_filter:
                return

        if rule_names_filter := self.configuration.get("rule_names_filter"):
            if alert["rule"]["name"] not in rule_names_filter:
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
            "comment": {
                "uuid": comment.get("uuid"),
                "content": comment.get("content"),
                "author": comment.get("created_by"),
                "date": comment.get("date"),
            },
            "file_path": file_path,
            "event_type": event_type,
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
            event_name=f"Sekoia.io Alert: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    @retry(
        reraise=True,
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(10),
    )
    def _retrieve_comment_from_alertapi(self, alert_uuid: str, comment_uuid: str):
        api_url = urljoin(
            self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}/comments/{comment_uuid}"
        )

        api_url = api_url.replace("/api/api", "/api")  # In case base_url ends with /api

        api_key = self.module.configuration["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()}

        response = requests.get(api_url, headers=headers)

        if not response.ok:
            try:
                content = response.json()
            except Exception:
                content = response.text
            self.log(
                "Error while fetching alert comment from Alert API",
                level="error",
                status_code=response.status_code,
                content=content,
            )

        # raise an exception if the http request failed
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exp:
            self.log("Failed to parse JSON response from Alert Comment API", level="error", content=response.text)
            raise exp
