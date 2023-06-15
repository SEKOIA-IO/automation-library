from functools import cached_property
from itertools import islice

from aws.s3.queued import AWSS3QueuedConfiguration, AWSS3QueuedConnector


class AWSS3LogsConfiguration(AWSS3QueuedConfiguration):
    ignore_comments: bool = False
    skip_first: int = 0
    separator: str


class AWSS3LogsTrigger(AWSS3QueuedConnector):
    configuration: AWSS3LogsConfiguration
    name = "AWS S3 Logs"

    @cached_property
    def separator(self):
        return self.configuration.separator

    @cached_property
    def ignore_comments(self):
        return self.configuration.ignore_comments

    @cached_property
    def skip_first(self):
        return self.configuration.skip_first

    def _parse_content(self, content: bytes) -> list:
        records = (record for record in content.decode("utf-8").split(self.separator) if len(record) > 0)

        if self.ignore_comments:
            records = (record for record in records if not record.strip().startswith("#"))

        return list(islice(records, self.skip_first, None))
