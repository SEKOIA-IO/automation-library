import signal
import time
from collections import defaultdict
from collections.abc import Generator
from functools import cached_property
from threading import Event
from typing import Any
from posixpath import join as urljoin

import orjson
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from cybereason_modules import CybereasonModule
from cybereason_modules.client import ApiClient
from cybereason_modules.client.auth import CybereasonApiAuthentication
from cybereason_modules.constants import (
    AI_HUNT_MALOP_DETAIL_ENDPOINT,
    AI_HUNT_MALOP_TYPES,
    MALOP_DETAIL_ENDPOINT,
    MALOP_INBOX_ENDPOINT,
)
from cybereason_modules.exceptions import InvalidJsonResponse, InvalidResponse, LoginFailureError, TimeoutError
from cybereason_modules.helpers import extract_models_from_malop, merge_suspicions, validate_response_not_login_failure
from cybereason_modules.logging import get_logger
from cybereason_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MALOPS, OUTCOMING_EVENTS

logger = get_logger()


class CybereasonEventConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    group_ids: list[str] | None = None
    chunk_size: int = 1000


class CybereasonEventConnector(Connector):
    """
    This connector fetches events from Cybereason API
    """

    module: CybereasonModule
    configuration: CybereasonEventConnectorConfiguration
    _stop_event: Event

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_date: int = (int(time.time()) - 60) * 1000  # milliseconds
        self._stop_event = Event()  # Event to notify we must stop the thread

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    @cached_property
    def client(self):
        """
        Return the HTTP client for the API

        :return: The HTTP client for the API
        :return: requests.Session
        """
        auth = CybereasonApiAuthentication(
            self.module.configuration.base_url, self.module.configuration.username, self.module.configuration.password
        )
        return ApiClient(auth=auth)

    def exit(self, _, __):
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    def parse_response_content(self, response: requests.Response) -> Any:
        """
        Parse the content of the response
        """
        if not validate_response_not_login_failure(response):
            raise LoginFailureError(response.url)

        try:
            return response.json()
        except Exception as error:
            raise InvalidJsonResponse(response) from error

    def fetch_malops(self, from_date: int, to_date: int) -> list[dict[str, Any]]:
        """
        Return a list of malops according the time range

        :param int from_date: The date from which
        """
        params: dict[str, Any] = {"startTime": from_date, "endTime": to_date}

        if self.configuration.group_ids is not None:
            params["groupIds"] = self.configuration.group_ids

        url = urljoin(self.module.configuration.base_url, MALOP_INBOX_ENDPOINT)
        try:
            logger.debug("Fetching malops", url=url, params=params)
            response = self.client.post(url, json=params, timeout=60)

            if not response.ok:
                self.log(
                    message=(
                        f"Request on Cybereason API to fetch events failed with status {response.status_code}"
                        f" - {response.reason}"
                    ),
                    level="error",
                )
                return []
            else:
                content = self.parse_response_content(response)
                malops = content.get("malops")

                if malops is None:
                    raise InvalidResponse(response)

                self.log(
                    message=f"Retrieved {len(malops)} events from Cybereason API with status {response.status_code}",
                    level="debug",
                )
                return malops
        except requests.Timeout as error:
            raise TimeoutError(url) from error

    def get_malop_detail(self, malop_uuid: str) -> dict[str, Any] | None:
        """
        Retrieve the detail of a malop
        """
        params: dict[str, str] = {"malopGuid": malop_uuid}

        url = urljoin(self.module.configuration.base_url, MALOP_DETAIL_ENDPOINT)
        response = self.client.post(url, json=params)

        if not response.ok:
            self.log(
                message=(
                    f"Request on Cybereason API to fetch detail for malop '{malop_uuid}' failed with status "
                    f"{response.status_code} - {response.reason}"
                ),
                level="error",
            )
            return None
        else:
            malop = self.parse_response_content(response)
            self.log(
                message=(
                    f"Request on Cybereason API to fetch detail for malop '{malop_uuid}' was a success "
                    f"(status {response.status_code})"
                ),
                level="debug",
            )
            return malop

    def get_edr_malop_suspicions(
        self, malop_uuid: str, requested_type: str
    ) -> dict[tuple[str, str], dict[str, Any]] | None:
        """
        Retrieve the suspicions and evidences for an EDR malop
        """
        params: dict[str, Any] = {
            "totalResultLimit": 10000,
            "perGroupLimit": 10000,
            "perFeatureLimit": 100,
            "templateContext": "OVERVIEW",
            "queryPath": [{"result": True, "guidList": [malop_uuid], "requestedType": requested_type}],
        }

        # call the api
        url = urljoin(self.module.configuration.base_url, AI_HUNT_MALOP_DETAIL_ENDPOINT)
        response = self.client.post(url, json=params)

        # check the response
        if not response.ok:
            self.log(
                message=(
                    f"Request on Cybereason API to fetch detail for malop '{malop_uuid}' failed with status "
                    f"{response.status_code} - {response.reason}"
                ),
                level="warning",
            )
            return None

        # get the results
        content = self.parse_response_content(response)
        data = content.get("data")

        if data is None:
            raise InvalidResponse(response)

        results = data.get("resultIdToElementDataMap", {})

        # Is the malop in the results?
        if malop_uuid not in results:
            return None

        # has the malop suspicions?
        suspicions = results[malop_uuid]["suspicions"]
        if suspicions is None:
            return None

        # Get the names of suspicions and the mapping
        suspicions_map = data["suspicionsMap"]

        # Select suspicions associated to the malop
        malop_suspicions = {
            (suspicion_id, suspicion_name): suspicions_map[suspicion_name]
            for suspicion_name, suspicion_id in suspicions.items()
        }

        return malop_suspicions

    def get_all_suspicions_for_edr_malop(self, malop_uuid: str) -> dict[tuple[str, str], dict[str, Any] | None] | None:
        """
        Retrieve all suspicions and evidences for an EDR malop
        """
        malop_suspicions: dict[tuple[str, str], dict[str, Any] | None] = defaultdict(lambda: {})

        # for each requested type
        for requested_type in AI_HUNT_MALOP_TYPES:
            # get suspicions
            suspicions = self.get_edr_malop_suspicions(malop_uuid, requested_type)

            # if no suspicions found, go to the next type
            if suspicions is None:
                continue

            # for found suspicions, merge them with ones from others types
            for suspicion_id, suspicion in suspicions.items():
                malop_suspicions[suspicion_id] = merge_suspicions(malop_suspicions[suspicion_id], suspicion)

        # If no suspicions found for any type, log it
        if len(malop_suspicions) == 0:
            self.log(
                message=f"No suspicions found for malop '{malop_uuid}'",
                level="info",
            )
            return None

        return malop_suspicions

    def enrich_generic_malop(self, malop: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
        """
        Get and yield details on the malop
        """
        # get details on the malop
        details = self.get_malop_detail(malop["guid"])

        # if no details retrieved, use the malop as base
        if details is None:
            users = malop.pop("users", [])
            machines = malop.pop("machines", [])
            yield malop
            yield from extract_models_from_malop(malop, users, ".UserInboxModel")
            yield from extract_models_from_malop(malop, machines, ".MachineInboxModel")
        else:
            users = details.pop("users", [])
            machines = details.pop("machines", [])
            file_suspects = details.pop("fileSuspects", [])
            yield details
            yield from extract_models_from_malop(details, users, ".UserDetailsModel")
            yield from extract_models_from_malop(details, machines, ".MachineDetailsModel")
            yield from extract_models_from_malop(details, file_suspects, ".FileSuspectDetailsModel")

    def fetch_last_events(self) -> Generator[dict[str, Any], None, None]:
        """
        Fetch the last malops from the Cybereason API
        """
        from_date = self.from_date
        now = int(time.time()) * 1000  # milliseconds

        # We don't retrieve messages older than one hour
        one_hour_ago = now - 3600000
        if from_date < one_hour_ago:
            from_date = one_hour_ago

        # compute the ending time to retrieve malops (Currently, now)
        to_date = now

        # fetch malops for the timerange
        next_malops = self.fetch_malops(from_date, to_date)
        INCOMING_MALOPS.labels(intake_key=self.configuration.intake_key).inc(len(next_malops))

        most_recent_date_seen = from_date
        for malop in next_malops:
            # save the greater date ever seen
            event_date = int(malop["lastUpdateTime"])
            if event_date > most_recent_date_seen:
                most_recent_date_seen = (
                    event_date + 1
                )  # add 1 milli-seconds to exclude the current malop from the next search

            # check if the malop is an AI Hunt malop (EDR) or a generic one
            is_edr = malop.get("edr", False)
            if is_edr:
                suspicions = self.get_all_suspicions_for_edr_malop(malop["guid"])

                users = malop.pop("users", [])
                machines = malop.pop("machines", [])
                yield malop
                yield from extract_models_from_malop(malop, users, ".UserInboxModel")
                yield from extract_models_from_malop(malop, machines, ".MachineInboxModel")
                if suspicions:
                    for (suspicion_uuid, suspicion_name), suspicion in suspicions.items():
                        if suspicion is not None:
                            yield {
                                "metadata": {"malopGuid": malop["guid"], "timestamp": malop["lastUpdateTime"]},
                                "@class": ".SuspicionModel",
                                "name": suspicion_name,
                                "guid": suspicion_uuid,
                                "firstTimestamp": suspicion["firstTimestamp"],
                                "evidences": suspicion["evidences"],
                            }

            else:
                yield from self.enrich_generic_malop(malop)

        # save the most recent date and compute the lag
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            current_lag = int(time.time() - (most_recent_date_seen / 1000))
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def next_batch(self):
        """
        Retrieve and forward the most recent malops
        """
        # save the starting time
        batch_start_time = time.time()

        # Fetch next events
        batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.fetch_last_events()]

        if len(batch_of_events) > 0:
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
            self.push_events_to_intakes(events=batch_of_events)
        else:
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetch and forward {len(batch_of_events)} events in {batch_duration} seconds",
            level="info",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self):
        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except LoginFailureError as error:
                self.log(message=f"Invalid username/password for {error.url}", level="error")
                time.sleep(self.configuration.frequency)
            except Exception as error:
                self.log_exception(error, message="Failed to fetch and forward events")
                time.sleep(self.configuration.frequency)
