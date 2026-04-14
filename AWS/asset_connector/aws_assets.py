"""Shared AWS asset connector base class.

This module centralizes authentication, checkpoint persistence, and AWS client
creation for AWS asset connectors.
"""

from typing import Optional

import boto3
from botocore.exceptions import NoCredentialsError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.storage import PersistentJSON
from aws_helpers.client import AwsClientConfiguration
from aws_helpers.oidc import OidcAwsMixin
from aws_helpers.base import AwsModule


class AwsAssetsConnector(OidcAwsMixin, AssetConnector):
    """Base class for AWS asset connectors sharing auth and checkpoint logic."""

    module: AwsModule

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.new_most_recent_date: Optional[str] = None

    @property
    def most_recent_date_seen(self) -> Optional[str]:
        """Get the most recent date seen from the checkpoint."""
        try:
            with self.context as cache:
                value = cache.get("most_recent_date_seen")
                return value if value is None or isinstance(value, str) else str(value)
        except Exception as e:
            self.log(f"Failed to retrieve checkpoint: {str(e)}", level="error")
            self.log_exception(e)
            return None

    def update_checkpoint(self) -> None:
        """Update checkpoint with the most recent processed date."""
        if self.new_most_recent_date is None:
            self.log("Warning: new_most_recent_date is None, skipping checkpoint update", level="warning")
            return

        try:
            with self.context as cache:
                cache["most_recent_date_seen"] = self.new_most_recent_date
                self.log(f"Checkpoint updated with date: {self.new_most_recent_date}", level="info")
        except Exception as e:
            self.log(f"Failed to update checkpoint: {str(e)}", level="error")
            self.log_exception(e)

    def get_client(self, service_name: str) -> boto3.client:
        """Create and return a configured AWS service client."""
        try:
            if self.module.configuration.aws_role_arn:
                aws_config: AwsClientConfiguration = self.get_assume_role()
                session = boto3.Session(
                    aws_access_key_id=aws_config.aws_access_key_id,
                    aws_secret_access_key=aws_config.aws_secret_access_key,
                    region_name=aws_config.aws_region,
                    aws_session_token=aws_config.aws_session_token,
                )
                return session.client(service_name)
            session = boto3.Session(
                aws_access_key_id=self.module.configuration.aws_access_key,
                aws_secret_access_key=self.module.configuration.aws_secret_access_key,
                region_name=self.module.configuration.aws_region_name,
            )
            return session.client(service_name)
        except NoCredentialsError as e:
            self.log("AWS credentials not found or invalid", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Failed to create AWS client for {service_name}: {str(e)}", level="error")
            self.log_exception(e)
            raise
