"""Contains AwsS3ParquetRecordsTrigger."""
import io
import ipaddress
from collections.abc import Sequence
from typing import Any

import orjson
import pandas

from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3ParquetRecordsTrigger(AbstractAwsS3QueuedConnector):
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

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse the content of the object and return a list of records.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        if len(content) == 0:
            return []

        # TODO: Check if we should save file locally with aiofiles and read it with pandas
        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)

        records = []
        for record in df.to_dict(orient="records"):
            if len(record) > 0 and not self.check_all_ips_are_private(record, ("srcaddr", "dstaddr")):
                records.append(orjson.dumps(record).decode("utf-8"))

        return records
