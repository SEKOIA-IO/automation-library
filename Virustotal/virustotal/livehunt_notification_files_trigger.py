import logging
import os
import time
from traceback import format_exc

from sekoia_automation.exceptions import SendEventError
from sekoia_automation.storage import PersistentJSON, write
from sekoia_automation.trigger import Trigger

from virustotal.api import VirusTotalV3API


class LivehuntNotificationFilesTrigger(Trigger, VirusTotalV3API):
    """
    Trigger that gets the new VirusTotal Livehunt notifications
    """

    BASE_URL = "intelligence/hunting_notification_files"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
        logging.basicConfig(
            level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
            format=FORMAT,
        )
        self._logger = logging.getLogger(__name__)

    @property
    def sleep_time(self):
        return int(self.configuration.get("sleep_time", 300))

    @property
    def skip_history(self):
        return self.configuration.get("skip_history", False)

    def run(self):
        self._logger.info("Started LiveHunt Trigger")

        while True:
            try:
                self.get_new_notifications()
            except SendEventError:
                # We were not able to send the notifications
                # Next time we will retry starting from the same point
                pass
            except Exception:
                self._logger.error(f"An unknown exception occured: {format_exc()}")

            time.sleep(self.sleep_time)

    def get_notifications(self, cursor=None):
        url = self.BASE_URL

        if cursor:
            url = f"{self.BASE_URL}?cursor={cursor}"

        response = self.request("GET", url)
        response.raise_for_status()

        return response.json()

    def save_last_notification(self, cache, notification):
        cache["last_notification_id"] = notification["context_attributes"]["notification_id"]
        cache["last_notification_date"] = notification["context_attributes"]["notification_date"]

    def get_new_notifications(self):
        with PersistentJSON("notifications.json", data_path=self._data_path) as cache:
            last_notification_id = cache.get("last_notification_id")
            last_notification_date = cache.get("last_notification_date")

            notifications = 0
            done = False
            cursor = None

            while not done:
                response = self.get_notifications(cursor)

                if response.get("meta") and response["meta"].get("cursor"):
                    cursor = response["meta"]["cursor"]
                else:
                    done = True

                if len(response["data"]) == 0:
                    break

                for notification in response["data"]:
                    if last_notification_id and last_notification_date:
                        if (notification["context_attributes"]["notification_id"] == last_notification_id) or (
                            notification["context_attributes"]["notification_date"] < last_notification_date
                        ):
                            done = True
                            break
                    # We are on the first run, ever
                    # If skip_history is True, we only save the last notification so that we have a starting point
                    elif self.skip_history:
                        self.save_last_notification(cache, notification)
                        done = True
                        break

                    self.process_notification(notification)

                    if notifications == 0:
                        self.save_last_notification(cache, notification)

                    notifications += 1

    def process_notification(self, notification):
        # Save the notification to a file
        filepath = write("notification.json", notification, data_path=self._data_path)

        # Extract relevant metadata
        event = {
            "ruleset_name": notification["context_attributes"]["ruleset_name"],
            "rule_name": notification["context_attributes"]["rule_name"],
            "notification_id": notification["context_attributes"]["notification_id"],
            "notification_date": notification["context_attributes"]["notification_date"],
            "md5": notification["attributes"]["md5"],
            "sha1": notification["attributes"]["sha1"],
            "sha256": notification["attributes"]["sha256"],
            "notification_path": "notification.json",
        }

        if notification["attributes"].get("meaningful_name"):
            event["name"] = notification["attributes"]["meaningful_name"]

        name = f'{event["ruleset_name"]} / {event["rule_name"]} / {event["sha256"]}'

        # Send the event
        self.send_event(name, event, filepath.parent.as_posix(), remove_directory=True)
