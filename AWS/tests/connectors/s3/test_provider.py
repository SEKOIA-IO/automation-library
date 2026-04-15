"""Tests for AwsAccountProvider."""

from unittest.mock import MagicMock, patch

import pytest
from faker import Faker

from aws_helpers.s3_wrapper import S3Wrapper
from aws_helpers.sqs_wrapper import SqsWrapper
from aws_helpers.base import AwsModuleConfiguration
from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.provider import AwsAccountProvider


@pytest.fixture
def aws_module_no_role(faker: Faker) -> AwsModule:
    """Module configured with access key (no role ARN)."""
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key=faker.word(),
        aws_secret_access_key=faker.word(),
        aws_region_name="us-west-2",
        base_url="https://test.sekoia.io",
    )
    return module


@pytest.fixture
def aws_module_with_role(faker: Faker) -> AwsModule:
    """Module configured with a role ARN triggering OIDC assumption."""
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key=None,
        aws_secret_access_key=None,
        aws_region_name="us-west-2",
        base_url="https://test.sekoia.io",
        aws_role_arn="arn:aws:iam::123456789012:role/TestRole",
    )
    return module


@pytest.fixture
def queued_config(faker: Faker) -> AwsS3QueuedConfiguration:
    return AwsS3QueuedConfiguration(
        intake_key=faker.word(),
        queue_name=faker.word(),
    )


def _make_provider(module: AwsModule, config: AwsS3QueuedConfiguration) -> AwsAccountProvider:
    """Create a minimal concrete AwsAccountProvider instance."""
    provider = AwsAccountProvider.__new__(AwsAccountProvider)
    provider.module = module
    provider.configuration = config
    return provider


class TestAwsAccountProviderNoRole:
    """Tests when aws_role_arn is not set – uses access key credentials."""

    def test_s3_wrapper_returns_s3_wrapper(self, aws_module_no_role, queued_config):
        provider = _make_provider(aws_module_no_role, queued_config)
        wrapper = provider.s3_wrapper
        assert isinstance(wrapper, S3Wrapper)

    def test_sqs_wrapper_returns_sqs_wrapper(self, aws_module_no_role, queued_config):
        provider = _make_provider(aws_module_no_role, queued_config)
        wrapper = provider.sqs_wrapper
        assert isinstance(wrapper, SqsWrapper)

    def test_s3_wrapper_uses_access_key_credentials(self, aws_module_no_role, queued_config):
        provider = _make_provider(aws_module_no_role, queued_config)
        wrapper = provider.s3_wrapper
        assert wrapper._configuration.aws_access_key_id == aws_module_no_role.configuration.aws_access_key
        assert wrapper._configuration.aws_secret_access_key == aws_module_no_role.configuration.aws_secret_access_key
        assert wrapper._configuration.aws_region == aws_module_no_role.configuration.aws_region_name

    def test_sqs_wrapper_uses_access_key_credentials(self, aws_module_no_role, queued_config):
        provider = _make_provider(aws_module_no_role, queued_config)
        wrapper = provider.sqs_wrapper
        assert wrapper._configuration.aws_access_key_id == aws_module_no_role.configuration.aws_access_key
        assert wrapper._configuration.queue_name == queued_config.queue_name


class TestAwsAccountProviderWithRole:
    """Tests when aws_role_arn is set – uses OIDC-assumed credentials."""

    def _mock_assume_role(self):
        assumed = MagicMock()
        assumed.aws_access_key_id = "ASIA_KEY"
        assumed.aws_secret_access_key = "assumed_secret"
        assumed.aws_session_token = "assumed_token"
        assumed.aws_region = "us-west-2"
        return assumed

    def test_s3_wrapper_uses_assumed_role_credentials(self, aws_module_with_role, queued_config):
        provider = _make_provider(aws_module_with_role, queued_config)
        assumed = self._mock_assume_role()

        with patch.object(provider, "get_assume_role", return_value=assumed):
            wrapper = provider.s3_wrapper

        assert isinstance(wrapper, S3Wrapper)
        assert wrapper._configuration.aws_access_key_id == "ASIA_KEY"
        assert wrapper._configuration.aws_session_token == "assumed_token"

    def test_sqs_wrapper_uses_assumed_role_credentials(self, aws_module_with_role, queued_config):
        provider = _make_provider(aws_module_with_role, queued_config)
        assumed = self._mock_assume_role()

        with patch.object(provider, "get_assume_role", return_value=assumed):
            wrapper = provider.sqs_wrapper

        assert isinstance(wrapper, SqsWrapper)
        assert wrapper._configuration.aws_access_key_id == "ASIA_KEY"
        assert wrapper._configuration.aws_session_token == "assumed_token"
        assert wrapper._configuration.queue_name == queued_config.queue_name
