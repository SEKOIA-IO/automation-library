import time
from abc import ABCMeta, abstractmethod
from collections.abc import Generator, Sequence
from functools import cached_property
from pathlib import Path
from threading import Event, Thread
from typing import Any

from botocore.paginate import Paginator
from pydantic import BaseModel
from sekoia_automation.storage import PersistentJSON, get_data_path

from aws.base import AWSConnector
from aws.utils import get_content


class AWSS3Worker(Thread, metaclass=ABCMeta):
    def __init__(
        self,
        trigger: "AWSS3FetcherTrigger",
        prefix: str | None,
        data_path: Path | None = None,
    ):
        super().__init__()
        self.trigger = trigger
        self.prefix = prefix
        self._data_path = data_path or get_data_path()
        self.context = PersistentJSON("context.json", self.storage)
        self.marker: str | None = self.read_marker()
        self.alive = Event()

    @cached_property
    def storage(self):
        path = self.prefix or "default"
        directory = self._data_path.joinpath(path)

        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        return directory

    @cached_property
    def name(self):
        return self.trigger.name

    @cached_property
    def bucket_name(self):
        return self.trigger.bucket_name

    @cached_property
    def client(self):
        return self.trigger.new_session().client("s3")

    @cached_property
    def configuration(self):
        return self.trigger.configuration

    def log(self, *args, **kwargs):
        self.trigger.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.trigger.log_exception(*args, **kwargs)

    def send_records(self, records: list, event_name: str):
        self.trigger.send_records(records=records, event_name=event_name)

    def read_marker(self) -> str | None:
        """
        Get the marker from the previous run
        """
        with self.context as variables:
            return variables.get("marker")

    def commit_marker(self):
        """
        Save the current marker
        """
        if self.marker is not None:
            with self.context as variables:
                variables["marker"] = self.marker

    def _list_of_objects(self, marker: str | None) -> Paginator:
        kwargs = {
            "Bucket": self.bucket_name,
        }

        if marker:
            kwargs["StartAfter"] = marker

        if self.prefix:
            kwargs["Prefix"] = self.prefix

        paginator = self.client.get_paginator("list_objects_v2")
        return paginator.paginate(**kwargs)

    def get_last_key(self, marker: str | None) -> str | None:
        """
        Return the last known key in the bucket
        """
        pages = self._list_of_objects(marker)
        last_key = self.marker
        for response in pages:
            keys = (obj["Key"] for obj in response.get("Contents", []) if obj["Size"] > 0)
            for key in keys:
                if last_key is None or key > last_key:
                    last_key = key

        return last_key

    def _read_object(self, bucket: str, key: str) -> bytes:
        """
        Read the remote object
        """
        obj = self.client.get_object(Bucket=bucket, Key=key)
        return get_content(obj)

    @abstractmethod
    def _parse_content(self, content: bytes) -> list[Any]:
        raise NotImplementedError()

    def _fetch_next_objects(self, marker: str | None) -> Generator[str, None, None]:
        pages = self._list_of_objects(marker)
        for response in pages:
            list_of_objects = [obj["Key"] for obj in response.get("Contents", []) if obj["Size"] > 0]
            yield from list_of_objects

    def _fetch_events(self, bucket_name: str, objects: Generator[str, None, None]) -> Generator[Any, None, None]:
        """
        Fetch events from the list of objects as a generator

        :param str bucket_name: The name of the bucket name
        :param list objects: The list of objects to read
        :return: The list of events as a generator
        """
        for key in objects:
            content = self._read_object(bucket_name, key)
            yield from self._parse_content(content)

    def _move_marker(self, objects: Generator[str, None, None]) -> Generator[str, None, None]:
        """
        Move the marker according the objects fetched

        :param generator objects: The list of fetched objects as a generator
        :return: The list of fetched objects as a generator
        """

        for key in objects:
            # move the marker to the next object
            self.marker = key

            # yield the key of the current object
            yield key

    def _chunk_events(self, events: Sequence, chunk_size: int) -> Generator[list[Any], None, None]:
        """
        Group events by chunk

        :param sequence events: The events to group
        :param int chunk_size: The size of the chunk
        """
        chunk: list[Any] = []

        # iter over the events
        for event in events:
            # if the chnuk is full
            if len(chunk) >= chunk_size:
                # yield the current chunk and create a new one
                yield chunk
                chunk = []

            # add the event to the current chunk
            chunk.append(event)

        # if the last chunk is not empty
        if len(chunk) > 0:
            # yield the last chunk
            yield chunk

    def forward_events(self):
        # get next objects
        objects = self._fetch_next_objects(self.marker)

        # get and forward events
        try:
            events = self._fetch_events(self.bucket_name, self._move_marker(objects))
            chunks = self._chunk_events(events, self.configuration.chunk_size or 10000)
            for records in chunks:
                self.log(message=f"forwarding {len(records)} records", level="info")
                self.send_records(
                    records=list(records),
                    event_name=f"{self.name.lower().replace(' ', '-')}_{str(time.time())}",
                )
        except Exception as ex:
            self.log_exception(ex, message=f"Failed to forward events from {self.bucket_name}")

    def stop(self):
        self.alive.set()

    def run(self):
        self.log(message=f"{self.name} worker for '{self.prefix}' has started", level="info")

        # get the last key on the Bucket from the marker
        last_key = self.get_last_key(self.marker)
        # if found, set the last key as the marker
        if last_key:
            self.marker = last_key

        self.log(
            message=f"Start fetching events from {self.marker} for '{self.prefix}'",
            level="info",
        )

        while not self.alive.is_set():
            try:
                self.commit_marker()
                self.forward_events()
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.configuration.frequency)


class AWSS3FetcherConfiguration(BaseModel):
    frequency: int = 60
    chunk_size: int = 10000
    prefix: str | None = None
    bucket_name: str


class AWSS3FetcherTrigger(AWSConnector, metaclass=ABCMeta):
    """
    This trigger fetches content from objects stored on a S3 Bucket
    and forward them to the playbook run.

    Quick notes
    - depends on boto3
    - Pulling relies on local instance variable {marker}, hence this variable is logs when the triggers stops.
    """

    configuration: AWSS3FetcherConfiguration
    worker_class: type = AWSS3Worker

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.workers: dict[str, AWSS3Worker] = {}

    @property
    @abstractmethod
    def service(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def prefix_pattern(self) -> str:
        raise NotImplementedError()

    @cached_property
    def client(self):
        return self.session.client("s3")

    @cached_property
    def bucket_name(self):
        return self.configuration.bucket_name

    @cached_property
    def prefix(self):
        return self.configuration.prefix

    def prefixes(self) -> set[str]:
        if self.prefix:
            return {self.prefix}

        account_id = self.session.client("sts").get_caller_identity().get("Account")
        regions = set(self.session.get_available_regions(self.service))

        return {self.prefix_pattern.format(account_id=account_id, region=region) for region in regions}

    def start_worker(self, prefix: str):
        if prefix in self.workers:
            w = self.workers[prefix]
            if not w.is_alive():
                w.start()
            return

        self.log(f"Starting {self.name} worker for '{prefix}'", level="info")
        w = self.worker_class(self, prefix, data_path=self._data_path)
        self.workers[prefix] = w
        w.start()

    def manage_workers(self):
        for prefix in self.prefixes():
            self.start_worker(prefix)

    def run(self):
        self.log(message=f"Starting {self.name} Trigger", level="info")

        try:
            while True:
                self.manage_workers()
                time.sleep(900)
        finally:
            self.log(message=f"Stopping {self.name} Trigger", level="info")

            for worker in self.workers.values():
                worker.stop()

            for worker in self.workers.values():
                worker.join()
