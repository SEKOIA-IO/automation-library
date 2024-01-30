"""Some useful wrappers for AWS services."""

import io
from pathlib import Path
from unittest.mock import Mock

import orjson
from botocore.paginate import Paginator

S3_CONFIGURATIONS = {
    "list_objects_v2": {
        "more_results": "IsTruncated",
        "limit_key": "MaxKeys",
        "output_token": "NextContinuationToken",
        "input_token": "ContinuationToken",
        "result_key": ["Contents", "CommonPrefixes"],
    }
}

S3_REGIONS = {"eu-west-2", "eu-west-3", "us-east-1"}


class S3MockBase:
    def __init__(self, **options):
        pass

    def get_paginator(self, name):
        if hasattr(self, name) and name in S3_CONFIGURATIONS.keys():
            return Paginator(getattr(self, name), S3_CONFIGURATIONS[name], Mock())

        raise ValueError(f"Unsupported operation '{name}'")


def s3_mock(s3_objects: dict) -> type:
    class S3Mock(S3MockBase):
        def list_objects_v2(self, **kwargs):
            objects = list(s3_objects.items())

            if (start_after := kwargs.get("StartAfter")) is not None:
                for _ in range(len(objects)):
                    name, value = objects.pop(0)
                    if name > start_after:
                        objects.insert(0, (name, value))
                        break

            return {
                "Contents": [{"Key": name, "Size": len(value)} for name, value in objects],
            }

        def get_object(self, **kwargs):
            if kwargs.get("Key") in s3_objects:
                return {"Body": io.BytesIO(s3_objects[kwargs["Key"]])}

    return S3Mock


class S3MockNoContent(S3MockBase):
    def list_objects_v2(self, **kwargs):
        return {}

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO()}


class S3MockNoObject(S3MockBase):
    def list_objects_v2(self, **kwargs):
        return {}

    def get_object(self, **kwargs):
        raise Exception()


class STSMock:
    def __init__(self, **options):
        pass

    def get_caller_identity(self):
        return {"Account": "111111111111"}


class SQSMockBase:
    def get_queue_url(self, **kwagrs):
        return {"QueueUrl": "myqueue"}


class SQSQueue:
    def __init__(self, messages: list):
        self.messages = messages

    def receive_message(self, **kwargs):
        yield from self.messages


def sqs_mock(messages: list) -> type:
    class SQSMock(SQSMockBase):
        def receive_message(self, **kwargs):
            return {"Messages": [{"Body": message} for message in messages]}

        def delete_message_batch(self, Entries: list, **kwargs):
            return {"Successful": [{"Id": entry["Id"]} for entry in Entries]}

    return SQSMock


class SQSMockNoContent(SQSMockBase):
    def receive_message(self, **kwargs):
        return {}

    def delete_message_batch(self, Entries: list, **kwargs):
        return {"Successful": []}


def aws_regions():
    return S3_REGIONS


def read_file(storage: Path, directory: str, filename: str) -> list[str]:
    """
    Read a file from the storage.

    Args:
        storage: Path
        directory: str
        filename: str

    Returns:
        list[str]:
    """
    filepath = storage.joinpath(directory).joinpath(filename)
    with filepath.open("rb") as f:
        return orjson.loads(f.read())
