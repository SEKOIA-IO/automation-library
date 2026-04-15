from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Protocol
from urllib.parse import urljoin

import boto3
import requests
from aws_helpers.client import AwsClientConfiguration

from .base import AwsModule


class _OidcHost(Protocol):
    """Protocol describing what OidcAwsMixin expects from its concrete class."""

    module: AwsModule
    token: str
    logs_url: str
    callback_url: str
    _cached_aws_config: AwsClientConfiguration | None
    _config_expiration: datetime | None

    def _get_oidc_token(self) -> str: ...

    @cached_property
    def url(self) -> str: ...

    @cached_property
    def headers(self) -> dict[str, str]: ...

    @cached_property
    def base_url(self) -> str: ...


class OidcAwsMixin:
    """Mixin providing OIDC-based AWS role assumption.

    The concrete class must expose:
    - self.module.configuration with aws_region_name, aws_role_arn,
      base_url, and api_key fields (i.e. AwsModule with AwsModuleConfiguration).
    """

    _cached_aws_config: AwsClientConfiguration | None = None
    _config_expiration: datetime | None = None

    @cached_property
    def headers(self: _OidcHost) -> dict[str, str]:
        """Authorization headers for OIDC token request."""
        return {"Authorization": f"Bearer {self.token}"}

    @cached_property
    def base_url(self: _OidcHost) -> str:
        """Base URL for OIDC token endpoint."""
        base_url = self.logs_url.rsplit("/api/", 1)[0] if self.logs_url else None
        if not base_url:
            raise ValueError("logs_url is not configured in module configuration")
        return base_url

    @cached_property
    def url(self: _OidcHost) -> str:
        """OIDC token endpoint URL."""
        base_url = self.base_url
        if self.module.trigger_configuration_uuid:
            node_type = "trigger"
            node_uuid = self.module.trigger_configuration_uuid
        elif self.module.connector_configuration_uuid:
            node_type = "connector"
            node_uuid = self.module.connector_configuration_uuid
        else:
            node_type = "action"
            node_uuid = self.callback_url.rsplit("/", 2)[1] if self.callback_url else "unknown"
        return urljoin(
            base_url,
            f"api/v1/symphony/oidc/token?node_type={node_type}&node_uuid={node_uuid}&audience=sts.amazonaws.com",
        )

    def _get_oidc_token(self: _OidcHost) -> str:
        """Fetch OIDC token from the configured endpoint."""
        result = requests.get(self.url, headers=self.headers, timeout=60)
        if not result.ok:
            raise Exception(f"Could not get OIDC token: {result.status_code} - {result.text}")
        token: str = result.json().get("token")
        if not token:
            raise Exception("Could not get OIDC token: token not found in response")
        return token

    def get_assume_role(self: _OidcHost) -> AwsClientConfiguration:
        """Assume AWS role via OIDC web identity and return temporary credentials.

        Credentials are cached and reused until 5 minutes before expiration.
        """
        now = datetime.now(timezone.utc)
        if (
            self._cached_aws_config is not None
            and self._config_expiration is not None
            and self._config_expiration - timedelta(minutes=5) > now
        ):
            return self._cached_aws_config

        sts_client = boto3.client("sts", region_name=self.module.configuration.aws_region_name)
        try:
            oidc_token = self._get_oidc_token()
            response = sts_client.assume_role_with_web_identity(
                RoleArn=self.module.configuration.aws_role_arn,
                RoleSessionName="sekoia-automation-session",
                WebIdentityToken=oidc_token,
            )
            credentials = response["Credentials"]
            self._config_expiration = credentials["Expiration"]
            self._cached_aws_config = AwsClientConfiguration(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_region=self.module.configuration.aws_region_name,
                aws_session_token=credentials["SessionToken"],
            )
            return self._cached_aws_config
        except Exception as e:
            raise RuntimeError(f"Could not assume role: {str(e)}") from e
