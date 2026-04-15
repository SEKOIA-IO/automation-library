"""Tests for OidcAwsMixin."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from aws_helpers.client import AwsClientConfiguration

from aws_helpers.base import AwsModule, AwsModuleConfiguration
from aws_helpers.oidc import OidcAwsMixin


class ConcreteOidcClass(OidcAwsMixin):
    """Concrete implementation of OidcAwsMixin for testing."""

    def __init__(self, module: AwsModule, token: str = "test_token") -> None:
        self.module = module
        self.token = token
        self.logs_url = "https://test.sekoia.io/api/v1/logs"


@pytest.fixture
def aws_module_with_role() -> AwsModule:
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key="test_key",
        aws_secret_access_key="test_secret",
        aws_region_name="us-east-1",
        aws_role_arn="arn:aws:iam::123456789012:role/TestRole",
    )
    module._trigger_configuration_uuid = None
    module._connector_configuration_uuid = "test-connector-uuid"
    return module


@pytest.fixture
def oidc_instance(aws_module_with_role: AwsModule) -> ConcreteOidcClass:
    return ConcreteOidcClass(module=aws_module_with_role)


def test_url_property_connector(oidc_instance: ConcreteOidcClass):
    """Test that url uses node=connector when only connector_configuration_uuid is set."""
    expected = (
        "https://test.sekoia.io/api/v1/symphony/oidc/token"
        "?node_type=connector&node_uuid=test-connector-uuid&audience=sts.amazonaws.com"
    )
    assert oidc_instance.url == expected


def test_url_property_trigger(aws_module_with_role: AwsModule):
    """Test that url uses node=trigger when trigger_configuration_uuid is set."""
    aws_module_with_role._trigger_configuration_uuid = "test-trigger-uuid"
    instance = ConcreteOidcClass(module=aws_module_with_role)
    expected = (
        "https://test.sekoia.io/api/v1/symphony/oidc/token"
        "?node_type=trigger&node_uuid=test-trigger-uuid&audience=sts.amazonaws.com"
    )
    assert instance.url == expected


def test_headers_property(oidc_instance: ConcreteOidcClass):
    """Test that headers include the Bearer token from self.token."""
    assert oidc_instance.headers == {"Authorization": "Bearer test_token"}


def test_get_oidc_token_success(oidc_instance: ConcreteOidcClass):
    """Test successful OIDC token retrieval."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"token": "my_oidc_token"}

    with patch("aws_helpers.oidc.requests.get", return_value=mock_response):
        token = oidc_instance._get_oidc_token()

    assert token == "my_oidc_token"


def test_get_oidc_token_http_error(oidc_instance: ConcreteOidcClass):
    """Test that _get_oidc_token raises when response is not ok."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("aws_helpers.oidc.requests.get", return_value=mock_response):
        with pytest.raises(Exception, match="Could not get OIDC token: 401 - Unauthorized"):
            oidc_instance._get_oidc_token()


def test_get_oidc_token_missing_access_token(oidc_instance: ConcreteOidcClass):
    """Test that _get_oidc_token raises when access_token is absent in response."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {}

    with patch("aws_helpers.oidc.requests.get", return_value=mock_response):
        with pytest.raises(Exception, match="token not found in response"):
            oidc_instance._get_oidc_token()


def test_get_assume_role_success(oidc_instance: ConcreteOidcClass):
    """Test successful role assumption via OIDC."""
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)

    mock_sts = MagicMock()
    mock_sts.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_KEY",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": expiration,
        }
    }

    with (
        patch("aws_helpers.oidc.boto3.client", return_value=mock_sts),
        patch.object(oidc_instance, "_get_oidc_token", return_value="fake_oidc_token"),
    ):
        result = oidc_instance.get_assume_role()

    assert isinstance(result, AwsClientConfiguration)
    assert result.aws_access_key_id == "ASIA_KEY"
    assert result.aws_secret_access_key == "secret"
    assert result.aws_session_token == "token"
    assert result.aws_region == "us-east-1"


def test_get_assume_role_uses_cache(oidc_instance: ConcreteOidcClass):
    """Test that a valid cached config is returned without re-fetching."""
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    cached = MagicMock(spec=AwsClientConfiguration)
    oidc_instance._cached_aws_config = cached
    oidc_instance._config_expiration = future_expiry

    with (
        patch("aws_helpers.oidc.boto3.client") as mock_boto,
        patch.object(oidc_instance, "_get_oidc_token") as mock_token,
    ):
        result = oidc_instance.get_assume_role()

    mock_boto.assert_not_called()
    mock_token.assert_not_called()
    assert result is cached


def test_get_assume_role_refreshes_expired_cache(oidc_instance: ConcreteOidcClass):
    """Test that an expired cached config triggers a new token fetch."""
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=10)
    cached = MagicMock(spec=AwsClientConfiguration)
    oidc_instance._cached_aws_config = cached
    oidc_instance._config_expiration = past_expiry

    new_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_sts = MagicMock()
    mock_sts.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "NEW_KEY",
            "SecretAccessKey": "new_secret",
            "SessionToken": "new_token",
            "Expiration": new_expiry,
        }
    }

    with (
        patch("aws_helpers.oidc.boto3.client", return_value=mock_sts),
        patch.object(oidc_instance, "_get_oidc_token", return_value="fresh_oidc_token"),
    ):
        result = oidc_instance.get_assume_role()

    assert result.aws_access_key_id == "NEW_KEY"


def test_get_assume_role_exception_wrapping(oidc_instance: ConcreteOidcClass):
    """Test that exceptions from STS are wrapped with context message."""
    mock_sts = MagicMock()
    mock_sts.assume_role_with_web_identity.side_effect = Exception("STS down")

    with (
        patch("aws_helpers.oidc.boto3.client", return_value=mock_sts),
        patch.object(oidc_instance, "_get_oidc_token", return_value="oidc_token"),
    ):
        with pytest.raises(Exception, match="Could not assume role: STS down"):
            oidc_instance.get_assume_role()
