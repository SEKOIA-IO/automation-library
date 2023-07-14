import json
import os
import queue
import threading
import time
from collections.abc import Generator
from datetime import datetime, timedelta
from functools import cached_property

import orjson
from requests.auth import AuthBase
from requests.exceptions import HTTPError
from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.client import CrowdstrikeFalconClient, CrowdstrikeThreatGraphClient
from crowdstrike_falcon.exceptions import StreamNotAvailable
from crowdstrike_falcon.helpers import get_detection_id, group_edges_by_verticle_type
from crowdstrike_falcon.metrics import EVENTS_LAG, INCOMING_DETECTIONS, INCOMING_VERTICLES, OUTCOMING_EVENTS
from crowdstrike_falcon.models import CrowdStrikeFalconEventStreamConfiguration

MAX_EVENTS_PER_BATCH = 1000


class VerticlesCollector:
    def __init__(
        self,
        connector: "EventStreamTrigger",
        tg_client: CrowdstrikeThreatGraphClient,
        falcon_client: CrowdstrikeFalconClient | None = None,
    ):
        self.connector = connector
        self.falcon_client = falcon_client or connector.client
        self.tg_client = tg_client
        self.edge_types = set(self.tg_client.get_edge_types()) - {
            "device",
            "hunting_lead",
        }

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def get_graph_ids_from_detection(self, detection_details: dict) -> set[str]:
        """
        Extract graph ids from a detection

        :param dict detection_details: The detection
        :return: A set of graph ids extracted from the detection
        :rtype: set
        """
        # extract behaviors from the detection
        behaviors = detection_details.get("behaviors") or []

        # extract graph_ids from the behaviors
        graph_ids = set()
        for behavior in behaviors:
            # Get the triggering process graph id
            triggering_process_graph_id = behavior.get("triggering_process_graph_id")
            if triggering_process_graph_id is not None:
                graph_ids.add(triggering_process_graph_id)

            # Get the parent process graph id
            parent_process_graph_id = behavior.get("parent_details", {}).get("parent_process_graph_id")
            if parent_process_graph_id is not None:
                graph_ids.add(parent_process_graph_id)

        return graph_ids

    def collect_verticles_from_graph_ids(self, graph_ids: set[str]) -> Generator[tuple[str, str, dict], None, None]:
        """
        Collect verticles from a list of graph ids

        :param list: graph_ids: The list of sources to explore the graph
        """
        for graph_id in graph_ids:
            # iter over each type of edges
            for edge_type in self.edge_types:
                try:
                    # get edges starting from a graph id
                    edges = self.tg_client.list_edges(graph_id, edge_type)
                    groups = group_edges_by_verticle_type(edges)

                    # for each group, get the verticles
                    for verticle_type, list_of_edges in groups:
                        verticles_links = {edge["id"]: edge["source_vertex_id"] for edge in list_of_edges}
                        for vertex in self.tg_client.get_verticles_details(
                            list(verticles_links.keys()), verticle_type
                        ):
                            INCOMING_VERTICLES.labels(intake_key=self.connector.configuration.intake_key).inc()
                            yield (verticles_links[vertex["id"]], edge_type, vertex)
                except HTTPError as error:
                    self.log_exception(
                        error,
                        message=f"Failed to collect verticles for edge_type {edge_type} for graph_id {graph_id}",
                        level="warning",
                    )

    def collect_verticles_from_detection(self, detection_id: str) -> Generator[tuple[str, str, dict], None, None]:
        """
        Collect the verticles (events) from a detection

        :param str detection_id: The identifier of the detection
        """
        try:
            # get detection details from its identifier
            detection_details = next(self.falcon_client.get_detection_details(detection_ids=[detection_id]))

            # get graph ids from detection
            graph_ids = self.get_graph_ids_from_detection(detection_details)

            # for each group, get ther verticles
            yield from self.collect_verticles_from_graph_ids(graph_ids)
        except HTTPError as error:
            self.log_exception(
                error,
                message=(
                    f"Failed to collect verticles for detection {detection_id}: "
                    "{error.response.status_code} {error.response.reason}"
                ),
            )
        except Exception as error:
            self.log_exception(
                error,
                message=f"Failed to collect verticles for detection {detection_id}",
            )


class EventStreamAuthentication(AuthBase):
    def __init__(self, session_token: str):
        self.__session_token = session_token

    def __call__(self, request):
        request.headers["Authorization"] = f"Token {self.__session_token}"
        return request


class EventStreamReader(threading.Thread):
    def __init__(
        self,
        connector: "EventStreamTrigger",
        stream_root_url: str,
        stream_info: dict,
        offset: int = 0,
        client: CrowdstrikeFalconClient | None = None,
        verticles_collector: VerticlesCollector | None = None,
    ):
        super().__init__()
        self.connector = connector
        self.stream_root_url = stream_root_url
        self.stream_info = stream_info
        self.offset = offset
        self.client = client or connector.client
        self.verticles_collector = verticles_collector
        self.app_id = connector.app_id
        self.f_stop = connector.f_stop
        self.events_queue = connector.events_queue

    @cached_property
    def data_feed_url(self):
        data_feed_url = self.stream_info["dataFeedURL"]
        if self.offset:
            data_feed_url += f"&offset={self.offset}"

        return data_feed_url

    @cached_property
    def __authorization(self):
        return EventStreamAuthentication(self.stream_info["sessionToken"]["token"])

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def refresh_stream(self, refresh_url: str) -> None:
        """
        Refresh the stream
        """
        self.log(message=f"refresh the event stream {refresh_url}", level="debug")

        self.client.post(
            url=refresh_url,
            json={"action_name": "refresh_active_stream_session", "appId": self.app_id},
        )

        self.log(message=f"succesfully refreshed event stream {refresh_url}", level="info")

    def run(self) -> None:
        """
        Read the events transported by the specified stream.
        """

        next_refresh_at = datetime.utcnow() + timedelta(minutes=25)
        self.log(
            message=f"reading event stream {self.data_feed_url} starting on offset {self.offset}",
            level="info",
        )

        try:
            with self.client.get(
                url=self.data_feed_url,
                stream=True,
                timeout=(3.05, 60),
                auth=self.__authorization,
            ) as http_response:
                if http_response.status_code >= 400:
                    self.log(
                        (
                            f"Failed to connect on stream {self.data_feed_url}: "
                            f"status code is {http_response.status_code}. " + str(http_response.content)
                        ),
                        level="error",
                    )
                    raise StreamNotAvailable(http_response)

                while not self.f_stop.is_set():
                    if datetime.utcnow() >= next_refresh_at:
                        self.refresh_stream(refresh_url=self.stream_info["refreshActiveSessionURL"])
                        next_refresh_at = datetime.utcnow() + timedelta(minutes=25)

                    for line in http_response.iter_lines():
                        if line.strip():
                            try:
                                decoded_line = line.strip().decode()
                                # check the line is json
                                event = json.loads(decoded_line)
                                # store the new event in the queue along with it stream root url
                                self.events_queue.put((self.stream_root_url, decoded_line))
                                INCOMING_DETECTIONS.labels(intake_key=self.connector.configuration.intake_key).inc()

                                detection_id = get_detection_id(event)
                                self.collect_verticles(detection_id, event)

                            except Exception as any_exception:
                                self.log(
                                    message=f"failed to read line {line} from event stream {self.stream_root_url}",
                                    level="error",
                                )
                                self.log_exception(any_exception)

                        # we refresh the session every 25min
                        if datetime.utcnow() >= next_refresh_at:
                            self.refresh_stream(refresh_url=self.stream_info["refreshActiveSessionURL"])
                            next_refresh_at = datetime.utcnow() + timedelta(minutes=25)

                        # we exit the loop if the worker is stopping
                        if self.f_stop.is_set():
                            break

        except Exception as any_exception:
            self.log_exception(any_exception)
            raise
        finally:
            self.log(
                message=f"Stream reader on event stream {self.stream_root_url} stopped",
                level="info",
            )

    def collect_verticles(self, detection_id: str | None, detection_event: dict):
        if detection_id is None:
            self.log(message="Not a detection", level="info")
            return

        if self.verticles_collector is None:
            self.log(message="verticles collection disabled", level="info")
            return

        self.log(message=f"Collect verticles for detection :{detection_id}", level="info")

        event_content = detection_event.get("event", {})
        severity_name = event_content.get("SeverityName")
        severity_code = event_content.get("Severity")

        nb_verticles = 0
        for (
            source_vertex_id,
            edge_type,
            vertex,
        ) in self.verticles_collector.collect_verticles_from_detection(detection_id):
            nb_verticles += 1
            event = {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {"sourceVertexId": source_vertex_id, "type": edge_type},
                    "severity": {"name": severity_name, "code": severity_code},
                },
                "event": vertex,
            }
            self.events_queue.put((self.stream_root_url, orjson.dumps(event).decode()))

        self.log(message=f"Collected {nb_verticles} vertex", level="info")


class EventStreamTrigger(Connector):
    """
    This trigger request new events from CrowdStrike Falcon event stream
    """

    module: CrowdStrikeFalconModule
    configuration: CrowdStrikeFalconEventStreamConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.auth_token = None

        self.app_id = f"sio-{time.time()}"
        self.events_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.f_stop = threading.Event()

        self._network_sleep_on_retry = 60

    @cached_property
    def client(self):
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
        )

    @cached_property
    def verticles_collector(self) -> VerticlesCollector | None:
        if (
            self.configuration.tg_base_url is None
            or self.configuration.tg_username is None
            or self.configuration.tg_password is None
        ):
            self.log(
                message="ThreatGraphAPI client disable: no credentials supplied",
                level="info",
            )
            return None

        tg_client = CrowdstrikeThreatGraphClient(
            self.configuration.tg_base_url,
            self.configuration.tg_username,
            self.configuration.tg_password,
        )

        return VerticlesCollector(self, tg_client, self.client)

    def read_queue(self) -> None:
        """
        Forward the queue to the intake
        """

        while not self.f_stop.is_set():
            try:
                (stream_root_url, event) = self.events_queue.get(block=True, timeout=5)
                batch_of_events = [event]
                last_event_per_stream: dict[str, str] = {stream_root_url: event}

                try:
                    while len(batch_of_events) < MAX_EVENTS_PER_BATCH:
                        (stream_root_url, event) = self.events_queue.get(block=True, timeout=0.5)
                        last_event_per_stream[stream_root_url] = event
                        batch_of_events.append(event)

                except queue.Empty:
                    pass

                if batch_of_events:
                    self.log(
                        message=f"Forward {len(batch_of_events)} events to the intake",
                        level="info",
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                    self.push_events_to_intakes(events=batch_of_events)

                    now = time.time()

                    # store the last offset for each stream
                    with PersistentJSON("cache.json", self._data_path) as cache:
                        for (
                            stream_root_url,
                            last_event,
                        ) in last_event_per_stream.items():
                            metadata = orjson.loads(last_event).get("metadata", {})

                            last_event_offset = metadata.get("offset")
                            if last_event_offset:
                                # update the offset in the cache file
                                cache[stream_root_url] = last_event_offset

                            creation_time = metadata.get("eventCreationTime")
                            if creation_time:
                                lag = now - (creation_time / 1000)
                                EVENTS_LAG.labels(
                                    intake_key=self.configuration.intake_key, stream=stream_root_url
                                ).observe(lag)
            except queue.Empty:
                pass

    def get_streams(self) -> dict[str, dict]:
        """
        Query the CS EventStream API to retrieve the streams
        """
        streams: dict[str, dict] = {}

        self.log(message="fetch the available event streams", level="debug")

        resources = self.client.list_streams(self.app_id)
        for stream_info in resources:
            stream_root_url = stream_info["dataFeedURL"].split("?")[0]
            streams[stream_root_url] = stream_info

        self.log(message=f"succesfully found {len(streams.keys())} streams", level="info")

        return streams

    def start_streams(self, streams: dict) -> dict:
        # start a stream thread for each stream
        stream_threads: dict[str, threading.Thread] = dict()

        for stream_root_url, stream_info in streams.items():
            # read the stream offset
            with PersistentJSON("cache.json", self._data_path) as cache:
                stream_offset = cache.get(stream_root_url, 0)

            stream_threads[stream_root_url] = EventStreamReader(
                self,
                stream_root_url,
                stream_info,
                stream_offset,
                self.client,
                self.verticles_collector,
            )
            stream_threads[stream_root_url].start()

        return stream_threads

    def supervise_streams(self, streams: dict, stream_threads: dict):
        # if a stream thread is down, we will refresh all the stream readers
        restart_stream_readers = False
        for stream_root_url in streams.keys():
            stream_thread = stream_threads[stream_root_url]
            if not stream_thread.is_alive():
                self.log(
                    message=f"Stream reader on {stream_root_url} is down, restarting stream readers",
                    level="warning",
                )
                restart_stream_readers = True

        if restart_stream_readers:
            streams = self.get_streams()
            for stream_root_url, stream_info in streams.items():
                if stream_root_url not in stream_threads or not stream_threads[stream_root_url].is_alive():
                    # read the stream offset
                    with PersistentJSON("cache.json", self._data_path) as cache:
                        stream_offset = cache.get(stream_root_url, 0)

                    stream_threads[stream_root_url] = EventStreamReader(
                        self,
                        stream_root_url,
                        stream_info,
                        stream_offset,
                        self.client,
                        self.verticles_collector,
                    )
                    stream_threads[stream_root_url].start()

    def run(self):
        try:
            # start a thread to consume the internal event queue
            read_queue_thread = threading.Thread(target=self.read_queue)
            read_queue_thread.start()

            streams: dict[str, dict] = self.get_streams()
            stream_threads = self.start_streams(streams)

            while True:
                # if the read queue thread is down, we spawn a new one
                if not read_queue_thread.is_alive():
                    self.log(message="Event forwarder failed", level="error")
                    read_queue_thread = threading.Thread(target=self.read_queue)
                    read_queue_thread.start()

                self.supervise_streams(streams, stream_threads)

                if self.f_stop.is_set():
                    break

                time.sleep(5)

        finally:
            # just in case
            self.f_stop.set()
