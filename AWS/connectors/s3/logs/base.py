"""Contains base implementation of workers and threads."""

import time
from abc import ABCMeta, abstractmethod
from collections.abc import Generator, Sequence
from functools import cached_property
from pathlib import Path
from threading import Event, Thread
from typing import Any, Optional

from botocore.client import BaseClient
from botocore.paginate import Paginator
from pydantic.v1 import BaseModel
from sekoia_automation.storage import PersistentJSON, get_data_path

from aws_helpers.base import AWSConnector
from aws_helpers.utils import get_content


class AwsS3Worker(Thread, metaclass=ABCMeta):  # pragma: no cover
    """Implements logic for AwsS3Worker."""

    data_path: Path

    def __init__(
        self,
        trigger: "AwsS3FetcherTrigger",
        prefix: str | None,
        data_path: Path | None = None,
    ) -> None:
        """Initialize AwsS3Worker."""
        super().__init__()
        self.trigger = trigger
        self.prefix = prefix
        self.data_path = data_path or get_data_path()
        self.context = PersistentJSON("context.json", self.storage)
        self.marker: str | None = self.read_marker()
        self.alive = Event()

    @cached_property
    def storage(self) -> Path:
        """
        Get the storage directory.

        Returns:
            Path:
        """
        path = self.prefix or "default"
        directory = self.data_path.joinpath(path)

        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        return directory

    @cached_property
    def bucket_name(self) -> str:
        return self.trigger.bucket_name

    @cached_property
    def client(self) -> BaseClient:
        return self.trigger.new_session().client("s3")

    @cached_property
    def configuration(self) -> "AwsS3FetcherConfiguration":
        return self.trigger.configuration

    def log(self, *args: Any, **kwargs: Optional[Any]) -> None:
        self.trigger.log(*args, **kwargs)

    def log_exception(self, *args: Any, **kwargs: Optional[Any]) -> None:
        self.trigger.log_exception(*args, **kwargs)

    def send_records(self, records: list[str], event_name: str) -> None:
        self.trigger.send_records(records=records, event_name=event_name)

    def read_marker(self) -> str | None:
        """
        Get the marker from the previous run

        Returns:
            str | None:
        """
        with self.context as variables:
            result: str | None = variables.get("marker")

            return result

    def commit_marker(self) -> None:
        """Save the current marker."""
        if self.marker is not None:
            with self.context as variables:
                variables["marker"] = self.marker

    def _list_of_objects(self, marker: str | None = None) -> Paginator:
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

        Args:
            bucket_name: str
            objects: Generator[str, None, None]

        Yields:
            Any:
        """
        for key in objects:
            content = self._read_object(bucket_name, key)

            yield from self._parse_content(content)

    def _move_marker(self, objects: Generator[str, None, None]) -> Generator[str, None, None]:
        """
        Move the marker according the objects fetched

        Args:
            objects: Generator[str, None, None]

        Yields:
            str:
        """
        for key in objects:
            # move the marker to the next object
            self.marker = key

            # yield the key of the current object
            yield key

    @staticmethod
    def _chunk_events(events: Sequence[Any], chunk_size: int) -> Generator[list[Any], None, None]:
        """
        Group events by chunk

        Args:
            events: Sequence[Any]
            chunk_size: int

        Yields:
            list[Any]:
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

    def forward_events(self) -> None:
        # get next objects
        objects = self._fetch_next_objects(self.marker)

        # get and forward events
        try:
            events = self._fetch_events(self.bucket_name, self._move_marker(objects))
            chunks = self._chunk_events(list(events), self.configuration.chunk_size or 10000)
            for records in chunks:
                self.log(message=f"forwarding {len(records)} records", level="info")
                self.send_records(
                    records=list(records),
                    event_name=f"{self.trigger.name.lower().replace(' ', '-')}_{str(time.time())}",
                )
        except Exception as ex:
            self.log_exception(ex, message=f"Failed to forward events from {self.bucket_name}")

    def stop(self) -> None:
        self.alive.set()

    def run(self) -> None:
        self.log(message=f"{self.trigger.name} worker for '{self.prefix}' has started", level="info")

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


class AwsS3FetcherConfiguration(BaseModel):
    frequency: int = 60
    chunk_size: int = 10000
    prefix: str | None = None
    bucket_name: str


class AwsS3FetcherTrigger(AWSConnector, metaclass=ABCMeta):  # pragma: no cover
    """
    This trigger fetches content from objects stored on a S3 Bucket
    and forward them to the playbook run.

    Quick notes
    - depends on boto3
    - Pulling relies on local instance variable {marker}, hence this variable is logs when the triggers stops.
    """

    configuration: AwsS3FetcherConfiguration
    worker_class: type = AwsS3Worker
    workers: dict[str, AwsS3Worker] = {}

    @property
    @abstractmethod
    def service(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def prefix_pattern(self) -> str:
        raise NotImplementedError()

    @cached_property
    def client(self) -> BaseClient:
        return self.session.client("s3")

    @cached_property
    def bucket_name(self) -> str:
        return self.configuration.bucket_name

    @cached_property
    def prefix(self) -> str | None:
        return self.configuration.prefix

    def prefixes(self) -> set[str]:
        if self.prefix:
            return {self.prefix}

        account_id = self.session.client("sts").get_caller_identity().get("Account")
        regions = set(self.session.get_available_regions(self.service))

        return {self.prefix_pattern.format(account_id=account_id, region=region) for region in regions}

    def start_worker(self, prefix: str) -> None:
        # Check if the worker is already running
        if prefix in self.workers:
            w = self.workers[prefix]
            if w.is_alive():
                return

        self.log(f"Starting {self.name} worker for '{prefix}'", level="info")
        w = self.worker_class(self, prefix, data_path=self._data_path)
        self.workers[prefix] = w
        w.start()

    def manage_workers(self) -> None:
        for prefix in self.prefixes():
            self.start_worker(prefix)

    def run(self) -> None:
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
