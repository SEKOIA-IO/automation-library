"""AWS User Asset Connector for collecting IAM user information.

This module provides functionality to collect AWS IAM user data and convert it
to OCSF User Inventory format for asset management and security monitoring.
"""

from collections.abc import Generator
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import pytz
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
    Group,
    User,
    UserOCSFModel,
)
from sekoia_automation.storage import PersistentJSON


class AwsUser:
    """Represents an AWS user with its metadata and creation date.

    Attributes:
        user: The OCSF User object containing user information
        date: The creation date of the user
    """

    def __init__(self, user: User, date: datetime) -> None:
        """Initialize an AwsUser instance.

        Args:
            user: The OCSF User object
            date: The creation date of the user
        """
        self.user = user
        self.date = date


class AwsUsersAssetConnector(AssetConnector):
    """Asset connector for collecting AWS IAM user information.

    This connector fetches IAM user data from AWS and converts it to OCSF
    User Inventory format for asset management and security monitoring.
    """

    PRODUCT_NAME: str = "AWS IAM"
    OCSF_VERSION: str = "1.6.0"
    PRODUCT_VERSION: str = "N/A"

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the AWS Users Asset Connector.

        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.new_most_recent_date: Optional[str] = None

    @property
    def most_recent_date_seen(self) -> Optional[str]:
        """Get the most recent date seen from the checkpoint.

        Returns:
            The most recent date as ISO string, or None if not set
        """
        try:
            with self.context as cache:
                value = cache.get("most_recent_date_seen")
                return value if value is None or isinstance(value, str) else str(value)
        except Exception as e:
            self.log(f"Failed to retrieve checkpoint: {str(e)}", level="error")
            self.log_exception(e)
            return None

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the most recent date.

        This method updates the persistent storage with the latest processed date
        to enable incremental data collection.
        """
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

    def client(self) -> boto3.client:
        """Create and return a configured AWS IAM client.

        Returns:
            A configured boto3 IAM client

        Raises:
            NoCredentialsError: If AWS credentials are not configured
            ClientError: If there's an error creating the client
        """
        try:
            session = boto3.Session(
                aws_access_key_id=self.module.configuration["aws_access_key"],
                aws_secret_access_key=self.module.configuration["aws_secret_access_key"],
                region_name=self.module.configuration["aws_region_name"],
            )
            return session.client("iam")
        except NoCredentialsError as e:
            self.log("AWS credentials not found or invalid", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Failed to create AWS client: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def get_groups_for_user(self, user_name: str) -> List[Group]:
        """Fetch groups associated with a specific user.

        Args:
            user_name: The name of the user to fetch groups for

        Returns:
            List of Group objects associated with the user

        Raises:
            ClientError: If there's an error communicating with AWS
            BotoCoreError: If there's a low-level boto3 error
        """
        if not user_name:
            self.log("Empty user name provided, returning empty groups list", level="warning")
            return []

        self.log(f"Fetching groups for user: {user_name}", level="debug")

        try:
            paginator = self.client().get_paginator("list_groups_for_user")
            page_iterator = paginator.paginate(UserName=user_name)
            groups = []

            for page in page_iterator:
                for group in page.get("Groups", []):
                    try:
                        group_obj = Group(
                            name=group.get("GroupName", ""),
                            uid=group.get("Arn", ""),
                        )
                        self.log(f"Fetched group: {group_obj.name} for user: {user_name}", level="debug")
                        groups.append(group_obj)
                    except Exception as e:
                        self.log(f"Failed to process group for user {user_name}: {str(e)}", level="error")
                        self.log_exception(e)
                        continue

            self.log(f"Successfully fetched {len(groups)} groups for user: {user_name}", level="debug")
            return groups

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self.log(f"AWS API error fetching groups for user {user_name} ({error_code}): {str(e)}", level="error")
            self.log_exception(e)
            raise
        except BotoCoreError as e:
            self.log(f"Boto3 core error fetching groups for user {user_name}: {str(e)}", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Unexpected error fetching groups for user {user_name}: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def get_mfa_status_for_user(self, user_name: str) -> bool:
        """Check if a user has MFA devices configured.

        Args:
            user_name: The name of the user to check MFA status for

        Returns:
            True if the user has MFA devices configured, False otherwise

        Raises:
            ClientError: If there's an error communicating with AWS
            BotoCoreError: If there's a low-level boto3 error
        """
        if not user_name:
            self.log("Empty user name provided, returning False for MFA status", level="warning")
            return False

        self.log(f"Checking MFA status for user: {user_name}", level="debug")

        try:
            response = self.client().list_mfa_devices(UserName=user_name)
            has_mfa = len(response.get("MFADevices", [])) > 0
            self.log(f"User {user_name} has MFA: {has_mfa}", level="debug")
            return has_mfa

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self.log(f"AWS API error checking MFA for user {user_name} ({error_code}): {str(e)}", level="error")
            self.log_exception(e)
            raise
        except BotoCoreError as e:
            self.log(f"Boto3 core error checking MFA for user {user_name}: {str(e)}", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Unexpected error checking MFA for user {user_name}: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def get_aws_users(self) -> Generator[List[AwsUser], None, None]:
        """Fetch AWS IAM users and convert them to AwsUser objects.

        Yields:
            Lists of AwsUser objects representing IAM users

        Raises:
            ClientError: If there's an error communicating with AWS
            BotoCoreError: If there's a low-level boto3 error
        """
        self.log("Starting AWS user collection...", level="info")

        try:
            paginator = self.client().get_paginator("list_users")
            page_iterator = paginator.paginate()

            # Parse the date filter for incremental collection
            date_filter: Optional[datetime] = None
            if self.most_recent_date_seen:
                try:
                    date_filter = isoparse(self.most_recent_date_seen)
                except (ValueError, TypeError) as e:
                    self.log(f"Invalid date format in checkpoint: {self.most_recent_date_seen}", level="warning")
                    self.log_exception(e)

            user_count = 0
            for page in page_iterator:
                users = []

                for user in page.get("Users", []):
                    try:
                        # Extract user information with proper error handling
                        aws_user = self._extract_user_from_iam_user(user, date_filter)
                        if aws_user:
                            users.append(aws_user)
                            user_count += 1
                    except Exception as e:
                        user_name = user.get("UserName", "unknown")
                        self.log(f"Failed to process user {user_name}: {str(e)}", level="error")
                        self.log_exception(e)
                        continue

                if users:
                    yield users

            self.log(f"Successfully collected {user_count} AWS users", level="info")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self.log(f"AWS API error ({error_code}): {str(e)}", level="error")
            self.log_exception(e)
            raise
        except BotoCoreError as e:
            self.log(f"Boto3 core error: {str(e)}", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Unexpected error during user collection: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def _extract_user_from_iam_user(self, user: Dict[str, Any], date_filter: Optional[datetime]) -> Optional[AwsUser]:
        """Extract user information from an AWS IAM user.

        Args:
            user: The AWS IAM user data
            date_filter: Optional date filter for incremental collection

        Returns:
            An AwsUser object if the user should be included, None otherwise
        """
        try:
            # Get user name and ARN
            user_name = user.get("UserName")
            user_arn = user.get("Arn")

            if not user_name or not user_arn:
                self.log("User missing UserName or Arn, skipping", level="warning")
                return None

            # Get creation time
            created_time = user.get("CreateDate")
            if not created_time:
                self.log(f"User {user_name} has no creation time, skipping", level="warning")
                return None

            # Ensure timezone is UTC
            if created_time.tzinfo is None:
                created_time = created_time.replace(tzinfo=pytz.UTC)
            elif created_time.tzinfo != pytz.UTC:
                created_time = created_time.astimezone(pytz.UTC)

            # Apply date filter for incremental collection
            if date_filter and created_time < date_filter:
                return None

            # Create account object
            account = Account(
                name=user_name,
                type=AccountTypeStr.AWS_ACCOUNT,
                type_id=AccountTypeId.AWS_ACCOUNT,
                uid=user_arn,
            )

            # Fetch groups and MFA status for the user
            try:
                groups = self.get_groups_for_user(user_name)
            except Exception as e:
                self.log(f"Failed to fetch groups for user {user_name}: {str(e)}", level="warning")
                groups = []

            try:
                has_mfa = self.get_mfa_status_for_user(user_name)
            except Exception as e:
                self.log(f"Failed to check MFA status for user {user_name}: {str(e)}", level="warning")
                has_mfa = False

            # Create user object
            user_obj = User(
                name=user_name,
                uid=user_arn,
                groups=groups,
                has_mfa=has_mfa,
                account=account,
            )

            self.log(f"Extracted user: {user_obj.name} ({user_arn})", level="debug")
            return AwsUser(user=user_obj, date=created_time)

        except Exception as e:
            user_name = user.get("UserName", "unknown")
            self.log(f"Error extracting user from IAM user {user_name}: {str(e)}", level="error")
            self.log_exception(e)
            return None

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Generate OCSF User Inventory events from AWS IAM users.

        Yields:
            UserOCSFModel objects representing user inventory events
        """
        self.log("Starting asset collection process...", level="info")
        self.log(f"Data path: {self._data_path.absolute()}", level="debug")

        try:
            # Set the checkpoint date at the start of collection
            new_most_recent_date = datetime.now().replace(tzinfo=pytz.UTC).isoformat()
            asset_count = 0

            for aws_users in self.get_aws_users():
                for aws_user in aws_users:
                    try:
                        # Create product and metadata
                        product = Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION)
                        metadata = Metadata(product=product, version=self.OCSF_VERSION)

                        # Create OCSF user inventory event
                        user_ocsf = UserOCSFModel(
                            activity_id=2,
                            activity_name="Collect",
                            category_name="Discovery",
                            category_uid=5,
                            class_name="User Inventory",
                            class_uid=5003,
                            type_name="User Inventory Info: Collect",
                            type_uid=500301,
                            time=aws_user.date.timestamp(),
                            metadata=metadata,
                            user=aws_user.user,
                        )

                        asset_count += 1
                        yield user_ocsf

                    except Exception as e:
                        self.log(f"Failed to create OCSF event for user {aws_user.user.uid}: {str(e)}", level="error")
                        self.log_exception(e)
                        continue

            # Update checkpoint with the new date
            self.new_most_recent_date = new_most_recent_date
            self.log(f"Asset collection completed. Generated {asset_count} user inventory events", level="info")

        except Exception as e:
            self.log(f"Error during asset collection: {str(e)}", level="error")
            self.log_exception(e)
            raise
