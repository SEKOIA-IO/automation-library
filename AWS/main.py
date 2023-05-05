from aws.base import AWSModule
from aws.s3.trigger_s3_logs import AWSS3LogsTrigger
from aws.s3.trigger_s3_parquet import AWSS3ParquetRecordsTrigger
from aws.s3.trigger_s3_records import AWSS3RecordsTrigger
from aws.sqs.trigger_sqs_messages import AWSSQSMessagesTrigger

if __name__ == "__main__":
    module = AWSModule()
    module.register(AWSS3LogsTrigger, "aws_s3_logs_trigger")
    module.register(AWSS3RecordsTrigger, "aws_s3_cloudtrail_records_trigger")
    module.register(AWSS3ParquetRecordsTrigger, "aws_s3_parquet_records_trigger")
    module.register(AWSSQSMessagesTrigger, "aws_sqs_messages_trigger")
    module.run()
