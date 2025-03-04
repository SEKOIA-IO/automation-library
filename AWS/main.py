"""Initialize module and all connectors."""

from sekoia_automation.loguru.config import init_logging

from connectors import AwsModule
from connectors.s3.logs.trigger_cloudtrail_logs import CloudTrailLogsTrigger
from connectors.s3.logs.trigger_flowlog_records import FlowlogRecordsTrigger
from connectors.s3.trigger_s3_cloudfront import AwsS3CloudFrontTrigger
from connectors.s3.trigger_s3_flowlogs import AwsS3FlowLogsTrigger
from connectors.s3.trigger_s3_flowlogs_parquet import AwsS3FlowLogsParquetRecordsTrigger
from connectors.s3.trigger_s3_logs import AwsS3LogsTrigger
from connectors.s3.trigger_s3_ocsf_parquet import AwsS3OcsfTrigger
from connectors.s3.trigger_s3_records import AwsS3RecordsTrigger
from connectors.trigger_sqs_messages import AwsSqsMessagesTrigger

if __name__ == "__main__":
    init_logging()

    module = AwsModule()

    module.register(CloudTrailLogsTrigger, "cloudtrail_logs_trigger")
    module.register(FlowlogRecordsTrigger, "flowlog_records_trigger")
    module.register(AwsS3LogsTrigger, "aws_s3_logs_trigger")
    module.register(AwsS3RecordsTrigger, "aws_s3_cloudtrail_records_trigger")
    module.register(AwsS3FlowLogsParquetRecordsTrigger, "aws_s3_flowlogs_parquet_records_trigger")
    module.register(AwsSqsMessagesTrigger, "aws_sqs_messages_trigger")
    module.register(AwsS3FlowLogsTrigger, "aws_s3_flowlogs_trigger")
    module.register(AwsS3CloudFrontTrigger, "aws_s3_cloudfront_trigger")
    module.register(AwsS3OcsfTrigger, "aws_s3_oscf_trigger")

    module.run()
