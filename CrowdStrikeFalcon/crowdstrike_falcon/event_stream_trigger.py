import json
import queue
import threading
import time
from collections.abc import Generator
from functools import cached_property

import orjson
from requests.auth import AuthBase
from requests.exceptions import HTTPError, StreamConsumedError
from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.timer import RepeatedTimer

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.client import CrowdstrikeFalconClient, CrowdstrikeThreatGraphClient
from crowdstrike_falcon.exceptions import StreamNotAvailable
from crowdstrike_falcon.helpers import (
    compute_refresh_interval,
    get_detection_id,
    get_epp_detection_composite_id,
    group_edges_by_verticle_type,
)
from crowdstrike_falcon.logging import get_logger
from crowdstrike_falcon.metrics import EVENTS_LAG, INCOMING_DETECTIONS, INCOMING_VERTICLES, OUTCOMING_EVENTS
from crowdstrike_falcon.models import CrowdStrikeFalconEventStreamConfiguration

logger = get_logger()

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

    def get_graph_ids_from_alert(self, alert_details: dict) -> set[str]:
        """
        Extract graph ids from an alert

        :param dict alert_details: The alert
        :return: A set of graph ids extracted from the alert
        :rtype: set
        """
        # extract graph_ids from the resources
        graph_ids = set()

        # Get the triggering process graph id
        triggering_process_graph_id = alert_details.get("triggering_process_graph_id")
        if triggering_process_graph_id is not None:
            graph_ids.add(triggering_process_graph_id)

        # Get the parent process graph id
        parent_process_graph_id = alert_details.get("parent_details", {}).get("process_graph_id")
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
                    f"{error.response.status_code} {error.response.reason}"
                ),
            )
        except Exception as error:
            self.log_exception(
                error,
                message=f"Failed to collect verticles for detection {detection_id}",
            )

    def collect_verticles_from_alert(self, composite_id: str) -> Generator[tuple[str, str, dict], None, None]:
        """
        Collect the verticles (events) from an alert

        :param str detection_id: The identifier of the alert
        """
        try:
            # get alert details from its identifier
            alert_details = next(self.falcon_client.get_alert_details(composite_ids=[composite_id]))

            # get graph ids from detection
            graph_ids = self.get_graph_ids_from_alert(alert_details)

            # for each group, get their verticles
            yield from self.collect_verticles_from_graph_ids(graph_ids)

        except HTTPError as error:
            if error.response.status_code == 403:
                # we don't have proper permissions - roll back to the old API
                self.connector.use_alert_api = False
                self.log(level="error", message="Not enough permissions to use Alert API - rollback to Detection API")

            self.log_exception(
                error,
                message=(
                    f"Failed to collect verticles for alert {composite_id}: "
                    f"{error.response.status_code} {error.response.reason}"
                ),
            )

        except Exception as error:
            self.log_exception(
                error,
                message=f"Failed to collect verticles for alert {composite_id}",
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
        app_id: str,
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
        self.app_id = app_id
        self._stop_event = threading.Event()
        self.events_queue = connector.events_queue
        self.refresh_timer = RepeatedTimer(self.refresh_interval, self.refresh_stream_timer)

    def stop_refresh(self):
        self.refresh_timer.stop()

    def stop(self):
        if self.refresh_timer:
            self.stop_refresh()
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @cached_property
    def data_feed_url(self):
        data_feed_url = self.stream_info["dataFeedURL"]
        if self.offset:
            data_feed_url += f"&offset={self.offset}"

        return data_feed_url

    @cached_property
    def __authorization(self):
        return EventStreamAuthentication(self.stream_info["sessionToken"]["token"])

    @property
    def refresh_interval(self) -> int:
        return compute_refresh_interval(int(self.stream_info["refreshActiveSessionInterval"]))

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def refresh_stream(self, refresh_url: str) -> None:
        """
        Refresh the stream
        """
        logger.debug("refresh the event stream", refresh_url={refresh_url})

        response = self.client.post(
            url=refresh_url,
            json={"action_name": "refresh_active_stream_session", "appId": self.app_id},
        )
        if not response.ok:
            logger.error(
                "Failed to refresh the event stream",
                refresh_url=refresh_url,
                status_code=response.status_code,
                content=response.text,
            )
            self.log(level="error", message="failed to refresh the event stream")
        else:
            logger.info("successfully refreshed event stream", refresh_url=refresh_url)

    def refresh_stream_timer(self):
        return self.refresh_stream(refresh_url=self.stream_info["refreshActiveSessionURL"])

    def run(self) -> None:
        """
        Read the events transported by the specified stream.
        """

        self.refresh_timer.start()
        self.log(
            message=f"Reading event stream {self.data_feed_url} starting at offset {self.offset}",
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
                    logger.error(
                        "Failed to connect on stream",
                        data_feed_url=self.data_feed_url,
                        status_code=http_response.status_code,
                        content=http_response.content,
                    )
                    raise StreamNotAvailable(http_response)

                while self.running:
                    try:
                        for line in http_response.iter_lines():
                            if line.strip():
                                try:
                                    decoded_line = line.strip().decode()
                                    # check the line is json
                                    event = json.loads(decoded_line)
                                    # store the new event in the queue along with it stream root url
                                    self.events_queue.put((self.stream_root_url, decoded_line))
                                    INCOMING_DETECTIONS.labels(
                                        intake_key=self.connector.configuration.intake_key
                                    ).inc()

                                    if self.connector.use_alert_api:
                                        alert_id = get_epp_detection_composite_id(event)
                                        self.collect_verticles_for_epp_detection(alert_id, event)

                                    detection_id = get_detection_id(event)
                                    self.collect_verticles(detection_id, event)

                                except Exception as any_exception:
                                    logger.error(
                                        "failed to read line from event stream",
                                        line=line,
                                        stream_root_url=self.stream_root_url,
                                    )
                                    self.log_exception(any_exception)
                                    raise any_exception

                            # we exit the loop if the worker is stopping
                            if not self.running:
                                break
                    except StreamConsumedError:
                        logger.warn(
                            "The datafeed was closed. Reopen it",
                            stream_root_url=self.stream_root_url,
                        )
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
            logger.info("Not a detection")
            return

        if self.verticles_collector is None:
            logger.info("verticles collection disabled")
            return

        logger.info("Collect verticles for detection", detection_id=detection_id)

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

    def collect_verticles_for_epp_detection(self, composite_id: str | None, detection_event: dict):
        if composite_id is None:
            logger.info("Not a epp detection")
            return

        if self.verticles_collector is None:
            logger.info("verticles collection disabled")
            return

        logger.info("Collect verticles for detection", composite_id=composite_id)

        event_content = detection_event.get("event", {})
        severity_name = event_content.get("SeverityName")
        severity_code = event_content.get("Severity")

        nb_verticles = 0
        for (
            source_vertex_id,
            edge_type,
            vertex,
        ) in self.verticles_collector.collect_verticles_from_alert(composite_id):
            nb_verticles += 1
            event = {
                "metadata": {
                    "detectionIdString": composite_id,
                    "eventType": "Vertex",
                    "edge": {"sourceVertexId": source_vertex_id, "type": edge_type},
                    "severity": {"name": severity_name, "code": severity_code},
                },
                "event": vertex,
            }
            self.events_queue.put((self.stream_root_url, orjson.dumps(event).decode()))

        self.log(message=f"Collected {nb_verticles} vertex", level="info")


class EventForwarder(threading.Thread):
    def __init__(
        self,
        connector: "EventStreamTrigger",
    ):
        super().__init__()
        self.connector = connector
        self.events_queue = connector.events_queue
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def run(self) -> None:
        """
        Forward the queue to the intake
        """

        while self.running:
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
                    OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key).inc(
                        len(batch_of_events)
                    )
                    self.connector.push_events_to_intakes(events=batch_of_events)

                    now = time.time()

                    # store the last offset for each stream
                    with PersistentJSON("cache.json", self.connector._data_path) as cache:
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
                                    intake_key=self.connector.configuration.intake_key, stream=stream_root_url
                                ).set(lag)
            except queue.Empty:
                pass
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")


class EventStreamTrigger(Connector):
    """
    This trigger request new events from CrowdStrike Falcon event stream
    """

    module: CrowdStrikeFalconModule
    configuration: CrowdStrikeFalconEventStreamConfiguration

    seconds_without_events = 3600 * 24  # Time to wait without events before restarting the pod

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.auth_token = None

        self.events_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.f_stop = threading.Event()

        self._network_sleep_on_retry = 60

        # Detect API will be taken down in favor of the Alert API as well as that
        # DetectionSummaryEvent will be replaced by EppDetectionSummaryEvent. By default,
        # we'll try to use the new API, but we'll fail if permissions are not set.
        self.use_alert_api = True

    def generate_app_id(self):
        return f"sio-{time.time()}"

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        """
        Return the default headers for the HTTP requests used in this connector.

        Returns:
            dict[str, str]:
        """
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    @cached_property
    def client(self):
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            default_headers=self._http_default_headers,
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

        try:
            tg_client = CrowdstrikeThreatGraphClient(
                self.configuration.tg_base_url,
                self.configuration.tg_username,
                self.configuration.tg_password,
                default_headers=self._http_default_headers,
            )

            return VerticlesCollector(self, tg_client, self.client)
        except Exception as error:
            self.log_exception(error, message="Failed to start the verticles collector")
            return None

    def get_streams(self, app_id: str) -> dict[str, dict]:
        """
        Query the CS EventStream API to retrieve the streams
        """
        streams: dict[str, dict] = {}

        self.log(message="fetch the available event streams", level="debug")

        resources = self.client.list_streams(app_id)
        for stream_info in resources:
            stream_root_url = stream_info["dataFeedURL"].split("?")[0]
            streams[stream_root_url] = stream_info

        self.log(message=f"succesfully found {len(streams.keys())} streams", level="info")

        return streams

    def start_streams(self, streams: dict, app_id: str) -> dict:
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
                app_id,
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
                logger.warning("Stream reader is down, restarting it", stream_root_url=stream_root_url)
                restart_stream_readers = True

        if restart_stream_readers:
            app_id = self.generate_app_id()
            streams = self.get_streams(app_id)
            for stream_root_url, stream_info in streams.items():
                if stream_root_url not in stream_threads or not stream_threads[stream_root_url].is_alive():
                    # read the stream offset
                    with PersistentJSON("cache.json", self._data_path) as cache:
                        stream_offset = cache.get(stream_root_url, 0)

                    stream_threads[stream_root_url] = EventStreamReader(
                        self,
                        stream_root_url,
                        stream_info,
                        app_id,
                        stream_offset,
                        self.client,
                        self.verticles_collector,
                    )
                    stream_threads[stream_root_url].start()

    def stop_streams(self, stream_threads: dict):
        for stream_thread in stream_threads.values():
            if stream_thread.is_alive():
                stream_thread.stop()

    def run(self):
        try:
            app_id: str = self.generate_app_id()
            streams: dict[str, dict] = self.get_streams(app_id)

            # start a thread to consume the internal event queue
            read_queue_thread = EventForwarder(self)
            read_queue_thread.start()

            # start threads to consume streams
            stream_threads = self.start_streams(streams, app_id)

            try:
                while self.running:
                    # if the read queue thread is down, we spawn a new one
                    if not read_queue_thread.is_alive():
                        self.log(message="Event forwarder failed", level="error")
                        read_queue_thread = EventForwarder(self)
                        read_queue_thread.start()

                    self.supervise_streams(streams, stream_threads)
                    time.sleep(5)
            finally:
                self.stop_streams(stream_threads)
                read_queue_thread.stop()

        except HTTPError as error:
            if error.response is not None and error.response.status_code == 429:
                self.log(message="The connector was rate-limited, waiting 1 minute before retrying.", level="warning")
                time.sleep(60)  # The authentication faces a ratelimit, sleep 1 minutes
            else:
                self.log_exception(error, message="Failed to fetch and forward events")
        except Exception as error:
            self.log_exception(error, message="Failed to fetch and forward events")
