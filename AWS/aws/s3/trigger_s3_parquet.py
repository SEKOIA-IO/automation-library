import io

import orjson
import pandas

from aws.s3.queued import AWSS3QueuedConnector


class AWSS3ParquetRecordsTrigger(AWSS3QueuedConnector):
    name = "AWS S3 Parquet records"

    def _parse_content(self, content: bytes) -> list:
        if len(content) == 0:  # pragma: no cover
            return []

        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)

        records = []
        for record in df.to_dict(orient="records"):  # pragma: no cover
            if len(record) > 0:
                records.append(orjson.dumps(record).decode("utf-8"))

        return records
