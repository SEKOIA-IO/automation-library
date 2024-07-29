import time
from posixpath import join as urljoin

import requests
from sekoia_automation.storage import PersistentJSON, write
from sekoia_automation.trigger import Trigger


class FeedConsumptionTrigger(Trigger):
    """
    This trigger fetches STIX objects from Sekoia.io feed API
    """

    API_URL_ADDITIONAL_PARAMETERS = ["skip_expired=true"]
    FILE_NAME = "stix_objects.json"
    frequency: int = 300  # Frequency in seconds, previous value 3600
    _STOP_EVENT_WAIT = 120

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.next_cursor = None
        self.resume_on_errors = False
        self.first_run = True

    @property
    def feed_id(self) -> str:
        return self.configuration.get("feed_id", "d6092c37-d8d7-45c3-8aff-c4dc26030608")

    @property
    def batch_size_limit(self) -> int:
        return self.configuration.get("batch_size_limit", 200)

    @property
    def modified_after(self) -> str | None:
        return self.configuration.get("modified_after")

    @property
    def url(self):
        url = (
            urljoin(
                self.module.configuration["base_url"],
                f"api/v2/inthreat/collections/{self.feed_id}/objects",
            )
            + f"?limit={self.batch_size_limit}"
            + f"&include_revoked={not self.first_run}"
        )
        url = url.replace("/api/api", "/api")  # In case base_url ends with /api
        if len(self.API_URL_ADDITIONAL_PARAMETERS) > 0:
            url += "&" + "&".join(self.API_URL_ADDITIONAL_PARAMETERS)

        with self.context as cache:
            cursor = cache.get("cursors", {}).get(self.feed_id)
            if cursor:
                return f"{url}&cursor={cursor}"
            elif self.modified_after:
                return f"{url}&modified_after={self.modified_after}"
            else:
                return url

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = (
                "Request on Sekoia.io feed API to fetch objects failed with status"
                f" {response.status_code} - {response.reason},"
                f"URL: {self.url}"
            )
            # Critical error will stop the trigger
            level = "error" if self.resume_on_errors else "critical"
            self.log(message=message, level=level)
            if not self.resume_on_errors:
                # Critical log should stop the trigger
                # So we wait until sigint is sent to the trigger
                self._stop_event.wait(self._STOP_EVENT_WAIT)
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

            event_name = f"Sekoia.io feed - batch of {len(objects)} objects"
            filepath = write(self.FILE_NAME, objects)
            self.send_event(
                event_name=event_name,
                event={"stix_objects_path": self.FILE_NAME},
                directory=filepath.parent.as_posix(),
                remove_directory=True,
            )

            # Store the cursor in the context for the next API call
            with self.context as cache:
                if "cursors" not in cache:
                    cache["cursors"] = {}
                cache["cursors"][self.feed_id] = self.next_cursor
        else:
            self.log(
                message="No objects fetched from the feed",
                level="info",
            )

        # Wait before launching the next batch if we reached the last updated object
        if len(objects) < self.batch_size_limit and not self._stop_event.is_set():
            self.first_run = False
            time.sleep(self.frequency)

    def run(self):
        self.log(message="Start SEKOIA feed consumption trigger", level="info")

        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except Exception as error:
                self.log(message="Failed to get data from feed", level="error")
                self.log_exception(error, message="Failed to get data from feed")


class FeedIOCConsumptionTrigger(FeedConsumptionTrigger):
    """
    This trigger fetches STIX IOC objects from Sekoia.io feed API
    """

    API_URL_ADDITIONAL_PARAMETERS = [
        "skip_expired=true",
        "include_revoked=false",
        "match[type]=indicator",
    ]
