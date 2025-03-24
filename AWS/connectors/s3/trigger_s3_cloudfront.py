"""Contains AwsS3CloudFrontTrigger."""

import datetime
import time
from collections.abc import AsyncGenerator
from itertools import groupby, islice
from typing import Any

import orjson
import pandas as pd

from aws_helpers.utils import AsyncReader
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration


class AwsS3CloudFrontConfiguration(AwsS3QueuedConfiguration):
    """AwsS3CloudFrontTrigger configuration."""

    skip_first: int = 0
    separator: str


class AwsS3CloudFrontTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3CloudFrontTrigger."""

    configuration: AwsS3CloudFrontConfiguration
    name = "AWS S3 CloudFront Logs"

    def data_to_kv(self, records: list[str]) -> Any:
        """
        Transform the raw data to key value data.
        """
        columns_name = records[0].split("Fields:", 1)[1].strip().split(" ")
        values = [record.split("\t") for record in records[1:]]
        df = pd.DataFrame(values, columns=columns_name)
        return df.to_dict(orient="records")

    def update_record(self, existing_entry: dict[str, Any], entry: dict[str, Any]) -> None:
        """
        Update record if there some similarity.
        """
        columns_name = list(existing_entry.keys())
        removed_list = [
            "date",
            "x-edge-location",
            "cs-ip",
            "cs-method",
            "cs(Host)",
            "cs-uri-stem",
            "sc-status",
            "x-edge-result-type",
        ]

        # To compare other columns
        for item in removed_list:
            removed_list.remove(item)

        for column in columns_name:
            if existing_entry[column] != "_":
                if existing_entry[column] != entry[column]:
                    existing_entry[column] = "_"

    def add_start_end_time(self, result: list[dict[str, Any]], agg_time: float) -> None:
        """
        Add start_time and end_time to each record.
        """
        for item in result:
            item.update({"start_time": item["time"]})
            start_timestamp = time.mktime(datetime.datetime.strptime(item["time"], "%H:%M:%S").timetuple())
            end_time = datetime.datetime.fromtimestamp(start_timestamp + agg_time).strftime("%H:%M:%S")
            item.update({"end_time": end_time})
            del item["time"]

    def records_to_json(self, results: list[dict[str, Any]]) -> list[str]:
        """
        Transform the records to str data.
        """
        return [orjson.dumps(result).decode("utf-8") for result in results]

    def logs_aggregation(self, data: list[dict[str, Any]]) -> list[str]:
        """
        Aggregate logs by date, time, x-edge-location, cs-ip, cs-method, cs(Host)
        cs-uri-stem, sc-status and x-edge-result-type
        """
        results = []
        start_aggregation = time.time()
        for _, group in groupby(
            data,
            lambda x: (
                x["date"],
                x["time"],
                x["x-edge-location"],
                x["c-ip"],
                x["cs-method"],
                x["cs(Host)"],
                x["cs-uri-stem"],
                x["sc-status"],
                x["x-edge-result-type"],
            ),
        ):
            group_list = list(group)
            agg_results: list[dict[str, Any]] = []
            count_agg = 1
            if len(group_list) >= 1:  # pragma: no cover
                for record in group_list:
                    existing_entry = next(
                        (
                            item
                            for item in agg_results
                            if (
                                item["date"] == record["date"]
                                and item["time"] == record["time"]
                                and item["x-edge-location"] == record["x-edge-location"]
                                and item["c-ip"] == record["c-ip"]
                            )
                        ),
                        None,
                    )

                    if existing_entry:
                        self.update_record(existing_entry, record)
                        count_agg += 1
                    else:
                        agg_results.append(record)
                agg_results[0]["count"] = count_agg
                group_list = agg_results
            results.append(group_list[0])
        end_aggregation = time.time()
        aggregation_time = end_aggregation - start_aggregation
        self.add_start_end_time(results, aggregation_time)

        return self.records_to_json(results)

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        content = await stream.read()
        records = [record for record in content.decode("utf-8").split(self.configuration.separator) if len(record) > 0]

        # return [] if there's no records
        if not records:
            return

        # Starting records from second element, skipping version
        kv_records = self.data_to_kv(records[1:])

        for record in list(islice(self.logs_aggregation(kv_records), self.configuration.skip_first, None)):
            yield record
