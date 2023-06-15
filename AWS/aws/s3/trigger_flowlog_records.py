from aws.s3.base import AWSS3FetcherTrigger, AWSS3Worker


class FlowlogRecordsWorker(AWSS3Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _parse_content(self, content: bytes) -> list[str]:
        return content.decode("utf-8").split("\n")[1:]


class FlowlogRecordsTrigger(AWSS3FetcherTrigger):
    """
    The Flowlog records trigger reads the next batch of logs published on the S3 bucket
    and forward them to the playbook run.
    """

    name = "AWS Flowlog"
    service = "ec2"
    worker_class = FlowlogRecordsWorker
    prefix_pattern = "AWSLogs/{account_id}/vpcflowlogs/{region}/"
