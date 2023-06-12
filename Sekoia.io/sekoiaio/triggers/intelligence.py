import signal
import time
from threading import Event
from urllib.parse import urljoin

import requests
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger


class FeedConsumptionTrigger(Trigger):
    """
    This trigger fetches STIX objects from SEKOIA.IO feed API
    """

    API_URL_ADDITIONAL_PARAMETERS = ["skip_expired=true", "include_revoked=false"]
    frequency: int = 3600  # Frequency in seconds
    batch_size_limit: int = 200

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)
        self.next_cursor = None
        self.resume_on_errors = False

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, _, __):
        self.log(message="Stopping Sekoia.io feed consumption trigger", level="info")
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @property
    def url(self):
        feed_id = self.configuration.get("feed_id", "d6092c37-d8d7-45c3-8aff-c4dc26030608")
        url = (
            urljoin(self.module.configuration["base_url"], f"v2/inthreat/collections/{feed_id}/objects")
            + f"?limit={self.__class__.batch_size_limit}"
        )
        if len(self.__class__.API_URL_ADDITIONAL_PARAMETERS) > 0:
            url += "&" + "&".join(self.__class__.API_URL_ADDITIONAL_PARAMETERS)

        with self.context as cache:
            cursor = cache.get("cursors", {}).get(self.configuration["feed_id"])
            if cursor:
                return f"{url}&cursor={cursor}"
            else:
                return url

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = (
                "Request on Sekoia.io feed API to fetch objects failed with status"
                f" {response.status_code} - {response.reason},"
                f"URL: {self.url}"
            )
            self.log(message=message, level="error")
            if not self.resume_on_errors:
                self._stop_event.set()
                response.raise_for_status()

    def fetch_objects(self):
        # Request the next batch of objects from the API
        api_key = self.module.configuration["api_key"]
        response = requests.get(self.url, headers={"Authorization": f"Bearer {api_key}"})

        # manage the response
        self._handle_response_error(response)

        # get objects from the response
        data = response.json()

        # Get cursor for next API call
        self.next_cursor = data.get("next_cursor", None)

        return data.get("items", [])

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        objects = self.fetch_objects()

        # Next runs will be continued in case of errors, as at least one run was ok
        self.resume_on_errors = True

        # compute the duration to fetch the objects
        batch_duration = int(time.time() - batch_start_time)
        self.log(
            message=f"Fetched objects in {batch_duration} seconds",
            level="debug",
        )

        if len(objects) > 0:
            self.log(
                message=f"Fetched {len(objects)} objects from the feed",
                level="info",
            )

            # Send objects as result of the trigger
            self.send_event(
                event_name=f"Sekoia.io feed - batch of {len(objects)} objects", event={"stix_objects": objects}
            )

            # Store the cursor in the context for the next API call
            with self.context as cache:
                if "cursors" not in cache:
                    cache["cursors"] = {}
                cache["cursors"][self.configuration["feed_id"]] = self.next_cursor
        else:
            self.log(
                message="No objects fetched from the feed",
                level="info",
            )

        # Wait before launching the next batch if we reached the last updated object
        if len(objects) < self.__class__.batch_size_limit and not self._stop_event.is_set():
            time.sleep(self.__class__.frequency)

    def run(self):
        self.log(message="Start SEKOIA feed consumption trigger", level="info")

        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to get data from feed")


class FeedIOCConsumptionTrigger(FeedConsumptionTrigger):
    """
    This trigger fetches STIX IOC objects from SEKOIA.IO feed API
    """

    API_URL_ADDITIONAL_PARAMETERS = ["skip_expired=true", "include_revoked=false", "match[type]=indicator"]
