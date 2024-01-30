"""Contains schemas for sqs messages."""

from pydantic import BaseModel


class FileInfoSchema(BaseModel):
    """File info schema that we receive from sqs."""

    path: str


class CrowdStrikeNotificationSchema(BaseModel):
    """
    Main sqs message schema.

    Contain only useful fields.

    Example of message with full list of fields:
    {
        "cid": "uuid",
        "timestamp": 1662307838018,
        "fileCount": 1,
        "totalSize": 13090,
        "bucket": "bucket-name",
        "pathPrefix": "path-prefix",
        "files": [
            {
                "path": "path-to-file",
                "size": 13090,
                "checksum": "checksum"
            }
        ]
    }
    """

    bucket: str
    files: list[FileInfoSchema]
