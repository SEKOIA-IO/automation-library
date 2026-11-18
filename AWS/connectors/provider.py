from __future__ import annotations

from typing import TYPE_CHECKING

from aws_helpers.base import AwsModule
from aws_helpers.client import AwsClientConfiguration
from aws_helpers.oidc import OidcAwsMixin
from aws_helpers.provider import AwsProvider
from aws_helpers.s3_wrapper import S3Configuration, S3Wrapper
from aws_helpers.sqs_wrapper import SqsConfiguration, SqsWrapper

if TYPE_CHECKING:
    from connectors.s3 import AwsS3QueuedConfiguration


class AwsAccountProvider(OidcAwsMixin, AwsProvider):
    """
    AWS provider with access key and secret access key.
    """

    module: AwsModule
    configuration: AwsS3QueuedConfiguration
    # one wrapper (and AWS session) per connector, rebuilt only when its configuration changes
    _s3_wrapper: S3Wrapper | None = None
    _sqs_wrapper: SqsWrapper | None = None

    def _reuse_s3_wrapper(self, config: S3Configuration) -> S3Wrapper:
        if self._s3_wrapper is None or self._s3_wrapper._configuration != config:
            self._s3_wrapper = S3Wrapper(config)
        return self._s3_wrapper

    def _reuse_sqs_wrapper(self, config: SqsConfiguration) -> SqsWrapper:
        if self._sqs_wrapper is None or self._sqs_wrapper._configuration != config:
            self._sqs_wrapper = SqsWrapper(config)
        return self._sqs_wrapper

    @property
    def s3_wrapper(self) -> S3Wrapper:
        """
        Get S3 wrapper.

        Returns:
            S3Wrapper:
        """
        if self.module.configuration.aws_role_arn:
            # If role ARN is provided, assume the role via OIDC and use the temporary credentials
            aws_config: AwsClientConfiguration = self.get_assume_role()  # type: ignore[misc]
            config = S3Configuration(
                aws_access_key_id=aws_config.aws_access_key_id,
                aws_secret_access_key=aws_config.aws_secret_access_key,
                aws_region=aws_config.aws_region,
                aws_session_token=aws_config.aws_session_token,
            )
            return self._reuse_s3_wrapper(config)
        config = S3Configuration(
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )
        return self._reuse_s3_wrapper(config)

    @property
    def sqs_wrapper(self) -> SqsWrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        if self.module.configuration.aws_role_arn:
            # If role ARN is provided, assume the role via OIDC and use the temporary credentials
            aws_config: AwsClientConfiguration = self.get_assume_role()  # type: ignore[misc]
            config = SqsConfiguration(
                frequency=self.configuration.sqs_frequency,
                delete_consumed_messages=self.configuration.delete_consumed_messages,
                queue_name=self.configuration.queue_name,
                aws_access_key_id=aws_config.aws_access_key_id,
                aws_secret_access_key=aws_config.aws_secret_access_key,
                aws_region=aws_config.aws_region,
                aws_session_token=aws_config.aws_session_token,
            )
            return self._reuse_sqs_wrapper(config)

        config = SqsConfiguration(
            frequency=self.configuration.sqs_frequency,
            delete_consumed_messages=self.configuration.delete_consumed_messages,
            queue_name=self.configuration.queue_name,
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )
        return self._reuse_sqs_wrapper(config)
