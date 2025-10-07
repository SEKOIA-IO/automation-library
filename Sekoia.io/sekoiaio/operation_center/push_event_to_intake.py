import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from posixpath import join as urljoin
from typing import Any, Generator, Sequence

import requests
from requests import Response
from sekoia_automation.action import Action
from sekoia_automation.constants import CHUNK_BYTES_MAX_SIZE, EVENT_BYTES_MAX_SIZE
from tenacity import Retrying, stop_after_delay, wait_exponential, retry_if_exception

from sekoiaio.utils import user_agent


class PushEventToIntake(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._executor = ThreadPoolExecutor(max_workers=5)

    def __del__(self):
        # Ensure the ThreadPoolExecutor is properly shut down
        executor = getattr(self, "_executor", None)
        if executor is not None:
            executor.shutdown(wait=True)

    def _delete_file(self, arguments: dict):
        event_path = arguments.get("event_path") or arguments.get("events_path")
        if event_path:
            filepath = self._data_path.joinpath(event_path)
            if filepath.is_file():
                filepath.unlink()

    def _retry(self):
        retry_on_status = {429, 500, 502, 503, 504}

        def retry_on_statuses(exception: Exception) -> bool:
            if isinstance(exception, requests.exceptions.RequestException):
                response = getattr(exception, "response", None)
                # Retry on connection errors and 5xx responses
                if response is None or response.status_code in retry_on_status:
                    return True
            return False

        return Retrying(
            stop=stop_after_delay(3600),  # 1 hour without being able to send events
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(retry_on_statuses),
            reraise=True,
        )

    def _chunk_events(self, events: Sequence) -> Generator[list[Any], None, None]:
        """
        Group events by chunk.

        Args:
            sequence events: Sequence: The events to group

        Returns:
            Generator[list[Any], None, None]:
        """
        chunk: list[Any] = []
        chunk_bytes: int = 0
        nb_discarded_events: int = 0

        # iter over the events
        for event in events:
            if len(event) > EVENT_BYTES_MAX_SIZE:
                nb_discarded_events += 1
                continue

            # if the chunk is full
            if chunk_bytes + len(event) > CHUNK_BYTES_MAX_SIZE:
                # yield the current chunk and create a new one
                yield chunk
                chunk = []
                chunk_bytes = 0

            # add the event to the current chunk
            chunk.append(event)
            chunk_bytes += len(event)

        # if the last chunk is not empty
        if len(chunk) > 0:
            # yield the last chunk
            yield chunk

        # if events were discarded, log it
        if nb_discarded_events > 0:
            self.log(message=f"{nb_discarded_events} too long events " "were discarded (length > 250kb)")

    def _send_chunk(
        self,
        intake_key: str,
        batch_api: str,
        chunk_index: int,
        chunk: list[Any],
        collect_ids: dict[int, list[str]],
    ):
        try:
            request_body = {
                "intake_key": intake_key,
                "jsons": chunk,
            }

            for attempt in self._retry():
                with attempt:
                    res: Response = requests.post(
                        batch_api, json=request_body, timeout=30, headers={"User-Agent": user_agent()}
                    )
                    res.raise_for_status()

            collect_ids[chunk_index] = res.json().get("event_ids", [])

        except Exception as ex:
            message = f"Failed to forward {len(chunk)} events"
            self.log(message=message, level="error")
            self.log_exception(ex, message=message)

    def run(self, arguments) -> dict:
        events = []

        arg_event = self.json_argument("event", arguments, required=False)
        if arg_event:
            if isinstance(arg_event, str):
                events.append(arg_event)
            else:
                events.append(json.dumps(arg_event))

        arg_events = self.json_argument("events", arguments, required=False) or []
        for event in arg_events:
            if isinstance(event, str):
                events.append(event)
            else:
                events.append(json.dumps(event))

        # no event to push
        if not events:
            self.log("No event to push", level="info")
            return {"event_ids": []}

        intake_server = arguments.get("intake_server", "https://intake.sekoia.io")
        batch_api = urljoin(intake_server, "batch")
        intake_key = arguments["intake_key"]

        # Dict to collect event_ids for the API
        collect_ids: dict[int, list] = {}

        chunks = self._chunk_events(events)
        # Forward chunks in parallel
        futures = [
            self._executor.submit(self._send_chunk, intake_key, batch_api, chunk_index, chunk, collect_ids)
            for chunk_index, chunk in enumerate(chunks)
        ]
        wait_futures(futures)

        event_ids = [event_id for chunk_index in sorted(collect_ids.keys()) for event_id in collect_ids[chunk_index]]

        if not arguments.get("keep_file_after_push", False):
            self._delete_file(arguments)

        return {"event_ids": event_ids}
