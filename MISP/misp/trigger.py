import logging
import os
import time
from traceback import format_exc

from cachetools import TTLCache
from misp.misp_query import MISPError, MISPQuery
from sekoia_automation.exceptions import SendEventError
from sekoia_automation.trigger import Trigger


class MISPTrigger(Trigger):
    """
    Trigger that gets the new MISP events on a regular basis
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
        logging.basicConfig(
            level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
            format=FORMAT,
        )
        self._logger = logging.getLogger(__name__)
        self._query = None
        self._old_ids = []

        self._attributes_cache = None

    @property
    def sleep_time(self):
        return int(self.configuration.get("sleep_time", 60))

    @property
    def attributes_filter(self):
        return int(self.configuration.get("attributes_filter", 0))

    @property
    def attributes_cache(self):
        if self._attributes_cache is None:
            self._attributes_cache = TTLCache(maxsize=100000, ttl=self.attributes_filter)

        return self._attributes_cache

    @property
    def query(self):
        if self._query is None:
            self._query = MISPQuery(
                url=self.module.configuration["misp_url"],
                key=self.module.configuration["misp_api_key"],
            )

        return self._query

    def run(self):
        self._logger.info("Started MISP Event Trigger")

        timestamp = time.time()
        while True:
            timestamp = self._run(timestamp)
            time.sleep(self.sleep_time)

    def _run(self, timestamp):
        # Get next timestamp before sending the requests
        # to be sure to not miss any event.
        next_timestamp = time.time()
        try:
            events = self.query.get_events_starting_from(timestamp)

            if events:
                self._logger.info(f"Processing {len(events)} events from MISP")
                self.process_new_events(events)

            timestamp = next_timestamp
        except (MISPError, SendEventError):
            # We were not able to retrieve the events
            # Next time we will retry starting from the same point
            pass
        except Exception:
            self._logger.error(f"An unknown exception happened: {format_exc()}")
            pass

        return timestamp

    def attribute_was_updated(self, attribute):
        """Check if an attribute is new / was updated"""
        after_timestamp = int(time.time()) - self.attributes_filter

        timestamp = int(attribute["timestamp"])
        was_updated = False

        if timestamp > after_timestamp:
            if attribute["uuid"] in self.attributes_cache:
                last_update = self.attributes_cache[attribute["uuid"]]

                if timestamp > last_update:
                    was_updated = True
            else:
                was_updated = True

        if was_updated:
            self.attributes_cache[attribute["uuid"]] = timestamp

        return was_updated

    def filter_attributes(self, event):
        """Filter out old attributes (according to `attributes_filter`)"""
        if self.attributes_filter:
            attributes = []
            objects = []
            context_attributes = []

            for attribute in event["Event"]["Attribute"]:
                if self.attribute_was_updated(attribute):
                    attributes.append(attribute)
                elif attribute["type"] in ["link", "text", "comment"] and attribute["category"] == "External analysis":
                    context_attributes.append(attribute)

            event["Event"]["Attribute"] = attributes

            for obj in event["Event"]["Object"]:
                if self.attribute_was_updated(obj):
                    objects.append(obj)

            event["Event"]["Object"] = objects

            # If there are some attributes left, add context generating attributes
            if event["Event"]["Attribute"] or event["Event"]["Object"]:
                event["Event"]["Attribute"] += context_attributes

        return event

    def process_new_events(self, events):
        ids = []
        for event in events:
            event_id = event["Event"]["id"]
            ids.append(event_id)

            if event_id in self._old_ids:
                # We already got this event in the previous query
                self._logger.info(f"Skipping event '{event_id}' because it was already retrieved")
                continue

            event = self.filter_attributes(event)

            if not (event["Event"]["Object"] or event["Event"]["Attribute"]):
                # Event does not contain any updated attribute
                self._logger.info(f"Skippink event '{event_id}' because it has no updated attribute")
                continue

            self._logger.info(f"Processing event '{event_id}'")
            self.send_event(event["Event"]["info"], {"event": event})

        self._old_ids = ids
