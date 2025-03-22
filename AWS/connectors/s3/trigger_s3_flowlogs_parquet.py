"""Contains AwsS3ParquetRecordsTrigger."""

import io
import ipaddress
from collections.abc import Sequence
from typing import Any

import orjson
import pandas

from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3FlowLogsParquetRecordsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3ParquetRecordsTrigger."""

    name = "AWS S3 Parquet records"

    def check_all_ips_are_private(self, record: dict[str, Any], names: Sequence[str]) -> bool:
        """
        Check if all IPs in a record are private

        Args:
            input_str: str

        Returns:
            bool:
        """
        ips = []
        for name in names:
            if name in record:
                try:
                    ips.append(ipaddress.ip_address(record[name]))
                except ValueError:  # if substring is not IP then just omit it
                    pass

        return all([ip.is_private for ip in ips])

    async def _process_content(self, content: bytes) -> int:
        """
        Parse the content of the object and return a list of records.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        if len(content) == 0:
            return 0

        # TODO: Check if we should save file locally with aiofiles and read it with pandas
        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)

        records = []
        total_count = 0

        for record in df.to_dict(orient="records"):
            if len(record) > 0:
                if not self.check_all_ips_are_private(record, ("srcaddr", "dstaddr")):
                    records.append(orjson.dumps(record).decode("utf-8"))
                    if len(records) >= self.limit_of_events_to_push:
                        total_count += len(await self.push_data_to_intakes(events=records))
                        records = []
                else:
                    DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

        if records:
            total_count += len(await self.push_data_to_intakes(events=records))

        return total_count
