import asyncio
import time
from asyncio import Queue
from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import Any, Optional, TypeAlias

import orjson
from loguru import logger
from pydantic import BaseModel
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import BitsightClient
from connectors import BitsightModule

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

FindingQueue: TypeAlias = Queue[tuple[dict[str, Any] | None, str]]
Finding: TypeAlias = dict[str, Any]


class CompanyCheckpoint(BaseModel):
    company_uuid: str
    last_seen: str | None = None
    offset: int | None = None

    def with_updated_last_seen(self) -> "CompanyCheckpoint":
        """
        Get CompanyCheckpoint with updated last_see corresponded to the next logic.

        If last_seen is None, then update it with 1 day before now and set offset to 0.
        If last_seen is not None and lower then 1 day before now, then update it with 1 day before now and set offset to 0.

        Format should be 'YYYY-MM-DD' corresponded to the Bitsight API:
            https://help.bitsighttech.com/hc/en-us/articles/360022913734-GET-Finding-Details

        Returns:
            datetime:
        """
        result = datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=0, hour=0) - timedelta(days=1)

        parsed_last_seen = (
            datetime.fromisoformat(self.last_seen).replace(tzinfo=timezone.utc) if self.last_seen else None
        )

        if parsed_last_seen is not None and parsed_last_seen >= result:
            return self

        return CompanyCheckpoint(company_uuid=self.company_uuid, last_seen=result.strftime("%Y-%m-%d"), offset=None)


class Checkpoint(BaseModel):
    values: list[CompanyCheckpoint] = []

    def get_company_checkpoint(self, company_uuid: str) -> CompanyCheckpoint:
        for value in self.values:
            if value.company_uuid == company_uuid:
                return value.with_updated_last_seen()

        return CompanyCheckpoint(company_uuid=company_uuid).with_updated_last_seen()

    def recalculate_company_checkpoint(self, company_uuid: str) -> None:
        company_checkpoint = self.get_company_checkpoint(company_uuid)
        if company_checkpoint is None:
            return

        last_seen = (
            datetime.fromisoformat(company_checkpoint.last_seen or datetime.now(timezone.utc).isoformat())
            .replace(tzinfo=timezone.utc)
            .replace(microsecond=0, second=0, minute=0, hour=0)
        )

        next_day = last_seen + timedelta(days=1)
        now = datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=0, hour=0)
        if next_day <= now:
            company_checkpoint.last_seen = next_day.strftime("%Y-%m-%d")
            company_checkpoint.offset = 1

        self.values = [value for value in self.values if value.company_uuid != company_uuid] + [company_checkpoint]

    def increment_company_checkpoint(self, company_uuid: str, last_seen: str) -> None:
        company_checkpoint = self.get_company_checkpoint(company_uuid)
        if company_checkpoint is None:
            company_checkpoint = CompanyCheckpoint(company_uuid=company_uuid, last_seen=last_seen, offset=0)

        checkpoint_last_seen_datetime = datetime.fromisoformat(company_checkpoint.last_seen or last_seen).replace(
            microsecond=0, second=0, minute=0, hour=0
        )

        last_seen_datetime = datetime.fromisoformat(last_seen)

        company_checkpoint.last_seen = last_seen

        if last_seen_datetime > checkpoint_last_seen_datetime:
            company_checkpoint.offset = 1
        elif last_seen_datetime == checkpoint_last_seen_datetime:
            company_checkpoint.offset = (company_checkpoint.offset or 0) + 1

        self.values = [value for value in self.values if value.company_uuid != company_uuid] + [company_checkpoint]


class PullFindingsConnectorConfiguration(DefaultConnectorConfiguration):
    """Connector configuration for Bitsight findings."""

    frequency: int = 10
    batch_limit: int = 10000


class PullFindingsConnector(AsyncConnector):
    """This connector fetches findings from Bitsight API"""

    _bitsight_client: BitsightClient | None = None

    module: BitsightModule
    configuration: PullFindingsConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init PullFindingsConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    def get_checkpoint(self) -> Checkpoint:
        """
        Get checkpoints.

        Returns:
            Checkpoint:
        """
        with self.context as cache:
            return Checkpoint.parse_obj(cache.get("checkpoints", {}))

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """
        Save checkpoints.

        Returns:
            Checkpoint:
        """
        logger.info("Saving checkpoint {0}", checkpoint.dict())
        with self.context as cache:
            cache["checkpoints"] = checkpoint.dict()

    @property
    def bitsight_client(self) -> BitsightClient:
        """
        Get async bitsight client.

        Returns:
            BitsightClient:
        """
        if self._bitsight_client is None:
            self._bitsight_client = BitsightClient(self.module.configuration.api_token)

        return self._bitsight_client

    @staticmethod
    def format_finding(finding: Finding, company_uuid: str) -> list[dict[str, Any]]:
        """
        Format finding.

        Args:
            finding: dict[str, Any]
            company_uuid: str

        Returns:
            list[dict[str, Any]]:
        """
        _finding = finding.copy()

        # Remove assets and vulnerabilities from finding
        assets = _finding.pop("assets", [])
        details = _finding.get("details", {})
        vulnerabilities = details.pop("vulnerabilities", [])
        _finding["details"] = details

        result = []

        for asset in assets:
            value = {**_finding, "company_uuid": company_uuid, "asset": asset}

            if len(vulnerabilities) > 0:
                for vulnerability in vulnerabilities:
                    result.append({**value, "vulnerability": vulnerability})
            else:
                result.append(value)

        return result

    async def process_findings_for_company(self, checkpoint: Checkpoint, company_id: str) -> int:
        last_seen = checkpoint.get_company_checkpoint(company_id).last_seen
        offset = checkpoint.get_company_checkpoint(company_id).offset

        logger.info(
            "Start to fetch findings for company {0} with last_seen {1} and offset {2}",
            company_id,
            last_seen,
            offset,
        )

        data_to_push = []
        total_pushed_events = 0

        async for finding in self.bitsight_client.findings_result(company_id, last_seen, offset):
            checkpoint.increment_company_checkpoint(company_id, finding["last_seen"])
            data_to_push.extend(self.format_finding(finding, company_id))

            if len(data_to_push) >= self.configuration.batch_limit:
                await self.push_data_to_intakes([orjson.dumps(event).decode("utf-8") for event in data_to_push])
                pushed_events = len(data_to_push)
                logger.info("Pushed {0} events to intakes", pushed_events)
                total_pushed_events += pushed_events
                data_to_push = []
                self.save_checkpoint(checkpoint)

        if len(data_to_push) > 0:
            await self.push_data_to_intakes([orjson.dumps(event).decode("utf-8") for event in data_to_push])
            pushed_events = len(data_to_push)
            logger.info("Pushed {0} events to intakes", pushed_events)
            total_pushed_events += pushed_events

        checkpoint.recalculate_company_checkpoint(company_id)
        self.save_checkpoint(checkpoint)

        # Add None to queue to indicate that all findings for this company have been fetched
        logger.info("Finished fetching findings for company {0}", company_id)

        return total_pushed_events

    async def next_batch(self) -> tuple[int, Checkpoint]:
        """
        Fetch next batch of findings.
        """
        logger.info("Start fetching next batch of findings. Companies {0}", self.module.configuration.company_uuids)
        checkpoint = self.get_checkpoint()

        company_ids = self.module.configuration.company_uuids

        processed_result: Any = [
            await self.process_findings_for_company(checkpoint, company) for company in company_ids
        ]

        pushed_events: int = reduce(lambda x, y: x + y, processed_result)
        logger.info("Finished with pushing events intakes. Total count is {0}", pushed_events)

        return pushed_events, self.get_checkpoint()

    def run(self) -> None:  # pragma: no cover
        """Runs Bitsight Pull Findings Connector."""

        self.log(message="Start fetching Bitsight findings", level="info")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            try:
                while self.running:
                    processing_start = time.time()
                    result_count, saved_checkpoint = loop.run_until_complete(self.next_batch())
                    processing_end = time.time()

                    last_event_date = max(
                        [
                            datetime.fromisoformat(checkpoint.last_seen)
                            for checkpoint in saved_checkpoint.values
                            if checkpoint.last_seen is not None
                        ]
                    )

                    # compute the lag if we got events
                    current_lag: int = 0
                    if result_count > 0:
                        current_lag = int(processing_end - last_event_date.timestamp())
                    else:
                        logger.info("No new events to forward")

                    # report the lag
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

                    # report the number of forwarded events
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(result_count)

                    # compute and report the duration to fetch the events
                    batch_duration = int(processing_end - processing_start)
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

                    # compute the remaining sleeping time. If greater than 0, sleep
                    delta_sleep = self.configuration.frequency - batch_duration
                    if delta_sleep > 0:
                        self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
                        time.sleep(delta_sleep)

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
