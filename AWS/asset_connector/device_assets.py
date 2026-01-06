"""AWS Device Asset Connector for collecting EC2 instance information.

This module provides functionality to collect AWS EC2 instance data and convert it
to OCSF Device Inventory format for asset management and security monitoring.
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
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    NetworkInterface,
    NetworkInterfaceTypeId,
    NetworkInterfaceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.storage import PersistentJSON

from aws_helpers.base import AWSModule


class AwsDevice:
    """Represents an AWS device with its metadata and creation date.

    Attributes:
        device: The OCSF Device object containing device information
        date: The creation/attachment date of the device
    """

    def __init__(self, device: Device, date: datetime) -> None:
        """Initialize an AwsDevice instance.

        Args:
            device: The OCSF Device object
            date: The creation/attachment date of the device
        """
        self.device = device
        self.date = date


class AwsDeviceAssetConnector(AssetConnector):
    """Asset connector for collecting AWS EC2 instance information.

    This connector fetches EC2 instance data from AWS and converts it to OCSF
    Device Inventory format for asset management and security monitoring.
    """

    module: AWSModule

    PRODUCT_NAME: str = "AWS EC2"
    OCSF_VERSION: str = "1.6.0"
    PRODUCT_VERSION: str = "N/A"

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the AWS Device Asset Connector.

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
        """Create and return a configured AWS EC2 client.

        Returns:
            A configured boto3 EC2 client

        Raises:
            NoCredentialsError: If AWS credentials are not configured
            ClientError: If there's an error creating the client
        """
        try:
            session = boto3.Session(
                aws_access_key_id=self.module.configuration.aws_access_key,
                aws_secret_access_key=self.module.configuration.aws_secret_access_key,
                region_name=self.module.configuration.aws_region_name,
            )
            return session.client("ec2")
        except NoCredentialsError as e:
            self.log("AWS credentials not found or invalid", level="error")
            self.log_exception(e)
            raise
        except Exception as e:
            self.log(f"Failed to create AWS client: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def _extract_network_interfaces(self, interfaces: List[Dict[str, Any]]) -> List[NetworkInterface]:
        """Extract network interface information from EC2 instance data.

        Args:
            interfaces: List of network interface data from EC2

        Returns:
            List of NetworkInterface objects
        """
        network_interfaces = []

        for interface in interfaces:
            try:
                # Extract basic interface information
                # AWS EC2 instances have wired network interfaces
                network_interface = NetworkInterface(
                    uid=interface.get("NetworkInterfaceId"),
                    name=interface.get("Description"),
                    mac=interface.get("MacAddress"),
                    ip=interface.get("PrivateIpAddress"),
                    hostname=interface.get("PrivateDnsName"),
                    type=NetworkInterfaceTypeStr.WIRED,
                    type_id=NetworkInterfaceTypeId.WIRED,
                )
                network_interfaces.append(network_interface)
            except Exception as e:
                self.log(f"Error extracting network interface: {str(e)}", level="warning")
                continue

        return network_interfaces

    def _extract_security_groups(self, security_groups: List[Dict[str, Any]]) -> List[Group]:
        """Extract security group information from EC2 instance data.

        Args:
            security_groups: List of security group data from EC2

        Returns:
            List of Group objects representing security groups
        """
        groups = []

        for sg in security_groups:
            try:
                # Map EC2 security groups to OCSF Group objects
                group = Group(
                    uid=sg.get("GroupId"),
                    name=sg.get("GroupName"),
                )
                groups.append(group)
            except Exception as e:
                self.log(f"Error extracting security group: {str(e)}", level="warning")
                continue

        return groups

    def _extract_name_from_tags(self, tags: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the Name tag value from EC2 instance tags.

        Args:
            tags: List of tag dictionaries from EC2 instance

        Returns:
            The value of the Name tag, or None if not found
        """
        for tag in tags:
            if tag.get("Key") == "Name":
                return tag.get("Value")
        return None

    def _extract_autoscale_group_from_tags(self, tags: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the autoscaling group name from EC2 instance tags.

        Args:
            tags: List of tag dictionaries from EC2 instance

        Returns:
            The autoscaling group name, or None if not found
        """
        for tag in tags:
            if tag.get("Key") == "aws:autoscaling:groupName":
                return tag.get("Value")
        return None

    def _extract_organization_from_owner_id(self, owner_id: str) -> Optional[Organization]:
        """Extract organization information from AWS Owner ID (account ID).

        Args:
            owner_id: The AWS account ID from the reservation

        Returns:
            Organization object with account ID, or None if not provided
        """
        if not owner_id:
            return None

        try:
            return Organization(
                name=f"AWS Account {owner_id}",
                uid=owner_id,
            )
        except Exception as e:
            self.log(f"Failed to create organization from owner ID {owner_id}: {str(e)}", level="warning")
            self.log_exception(e)
            return None

    def get_device_os(self, platform_details: str) -> OperatingSystem:
        """Determine the operating system from platform details.

        Args:
            platform_details: The platform details string from AWS

        Returns:
            An OperatingSystem object with the detected OS information
        """
        if not platform_details:
            return OperatingSystem(name="Unknown", type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

        platform_lower = platform_details.lower()

        if "windows" in platform_lower:
            return OperatingSystem(name="Windows", type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS)
        elif "linux" in platform_lower or "unix" in platform_lower:
            return OperatingSystem(name="Linux", type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
        elif "macos" in platform_lower or "mac" in platform_lower:
            return OperatingSystem(name="MacOS", type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
        else:
            return OperatingSystem(name=platform_details, type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

    def get_aws_devices(self) -> Generator[List[AwsDevice], None, None]:
        """Fetch AWS EC2 instances and convert them to AwsDevice objects.

        Yields:
            Lists of AwsDevice objects representing EC2 instances

        Raises:
            ClientError: If there's an error communicating with AWS
            BotoCoreError: If there's a low-level boto3 error
        """
        self.log("Starting AWS device collection...", level="info")

        try:
            paginator = self.client().get_paginator("describe_instances")
            page_iterator = paginator.paginate()

            # Parse the date filter for incremental collection
            date_filter: Optional[datetime] = None
            if self.most_recent_date_seen:
                try:
                    date_filter = isoparse(self.most_recent_date_seen)
                except (ValueError, TypeError) as e:
                    self.log(f"Invalid date format in checkpoint: {self.most_recent_date_seen}", level="warning")
                    self.log_exception(e)

            device_count = 0
            for page in page_iterator:
                devices = []

                for reservation in page.get("Reservations", []):
                    # Extract owner ID from reservation for organization info
                    owner_id = reservation.get("OwnerId")

                    for instance in reservation.get("Instances", []):
                        try:
                            # Extract device information with proper error handling
                            device = self._extract_device_from_instance(instance, date_filter, owner_id)
                            if device:
                                devices.append(device)
                                device_count += 1
                        except Exception as e:
                            instance_id = instance.get("InstanceId", "unknown")
                            self.log(f"Failed to process instance {instance_id}: {str(e)}", level="error")
                            self.log_exception(e)
                            continue

                if devices:
                    yield devices

            self.log(f"Successfully collected {device_count} AWS devices", level="info")

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
            self.log(f"Unexpected error during device collection: {str(e)}", level="error")
            self.log_exception(e)
            raise

    def _extract_device_from_instance(
        self, instance: Dict[str, Any], date_filter: Optional[datetime], owner_id: Optional[str] = None
    ) -> Optional[AwsDevice]:
        """Extract device information from an AWS instance.

        Args:
            instance: The AWS instance data
            date_filter: Optional date filter for incremental collection
            owner_id: Optional AWS account ID from the reservation

        Returns:
            An AwsDevice object if the instance should be included, None otherwise
        """
        try:
            # Get instance ID
            instance_id = instance.get("InstanceId")
            if not instance_id:
                self.log("Instance missing InstanceId, skipping", level="warning")
                return None

            # Get creation time from EBS attachment or launch time
            created_time = None
            boot_time = None
            if instance.get("BlockDeviceMappings"):
                # Try to get EBS attachment time
                ebs_info = instance["BlockDeviceMappings"][0].get("Ebs", {})
                attach_time = ebs_info.get("AttachTime")
                if attach_time:
                    # Parse datetime string if needed
                    if isinstance(attach_time, str):
                        created_time = isoparse(attach_time)
                    else:
                        created_time = attach_time

            # Fallback to launch time if no EBS attachment time
            launch_time = instance.get("LaunchTime")
            if not created_time and launch_time:
                # Parse datetime string if needed
                if isinstance(launch_time, str):
                    created_time = isoparse(launch_time)
                else:
                    created_time = launch_time

            # Use launch time as boot time
            if launch_time:
                # Parse datetime string if needed
                if isinstance(launch_time, str):
                    boot_time = isoparse(launch_time)
                else:
                    boot_time = launch_time

            if not created_time:
                self.log(f"Instance {instance_id} has no creation time, skipping", level="warning")
                return None

            # Ensure timezone is UTC
            if created_time.tzinfo is None:
                created_time = created_time.replace(tzinfo=pytz.UTC)
            elif created_time.tzinfo != pytz.UTC:
                created_time = created_time.astimezone(pytz.UTC)

            # Apply date filter for incremental collection
            if date_filter and created_time < date_filter:
                return None

            # Extract hostname (prefer PublicDnsName, fallback to PrivateDnsName)
            # Handle empty strings as None
            public_dns = instance.get("PublicDnsName") or None
            private_dns = instance.get("PrivateDnsName") or None
            hostname = public_dns or private_dns or instance_id

            # Extract name from tags
            name = self._extract_name_from_tags(instance.get("Tags", []))

            # Extract network interfaces
            network_interfaces = self._extract_network_interfaces(instance.get("NetworkInterfaces", []))

            # Extract security groups
            groups = self._extract_security_groups(instance.get("SecurityGroups", []))

            # Extract primary IP address
            ip_address = instance.get("PublicIpAddress") or instance.get("PrivateIpAddress")

            # Extract region from placement
            region = None
            if instance.get("Placement"):
                region = instance["Placement"].get("AvailabilityZone")

            # Extract subnet
            subnet = instance.get("SubnetId")

            # Extract VPC as domain
            domain = instance.get("VpcId")

            # Extract hypervisor
            hypervisor = instance.get("Hypervisor")

            # Extract vendor and model from instance type
            vendor_name = "Amazon Web Services"
            model = instance.get("InstanceType")

            # Extract autoscale group from tags
            autoscale_uid = self._extract_autoscale_group_from_tags(instance.get("Tags", []))

            # Build description from image ID and state
            image_id = instance.get("ImageId")
            state = instance.get("State", {}).get("Name")
            desc = f"AMI: {image_id}" if image_id else None
            if state:
                desc = f"{desc}, State: {state}" if desc else f"State: {state}"

            # Determine if managed (instances with IAM roles are considered managed)
            is_managed = instance.get("IamInstanceProfile") is not None

            # Format boot time as ISO string if available
            boot_time_str = None
            if boot_time:
                if boot_time.tzinfo is None:
                    boot_time = boot_time.replace(tzinfo=pytz.UTC)
                elif boot_time.tzinfo != pytz.UTC:
                    boot_time = boot_time.astimezone(pytz.UTC)
                boot_time_str = boot_time.isoformat()

            # Convert created_time to timestamp for created_time field
            created_timestamp = created_time.timestamp()

            # Extract organization from owner ID
            org = self._extract_organization_from_owner_id(owner_id) if owner_id else None

            # Create device object with all available fields
            device_obj = Device(
                type_id=DeviceTypeId.SERVER,
                type=DeviceTypeStr.SERVER,
                uid=instance_id,
                hostname=hostname,
                name=name,
                os=self.get_device_os(instance.get("PlatformDetails", "")),
                location=None,  # AWS doesn't provide city/country in EC2 API
                network_interfaces=network_interfaces if network_interfaces else None,
                groups=groups if groups else None,
                ip=ip_address,
                region=region,
                subnet=subnet,
                domain=domain,
                hypervisor=hypervisor,
                vendor_name=vendor_name,
                model=model,
                boot_time=boot_time_str,
                created_time=created_timestamp,
                is_managed=is_managed,
                autoscale_uid=autoscale_uid,
                desc=desc,
                org=org,
            )

            self.log(f"Extracted device: {device_obj.hostname} ({instance_id})", level="debug")
            return AwsDevice(device=device_obj, date=created_time)

        except Exception as e:
            instance_id = instance.get("InstanceId", "unknown")
            self.log(f"Error extracting device from instance {instance_id}: {str(e)}", level="error")
            self.log_exception(e)
            return None

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        """Generate OCSF Device Inventory events from AWS EC2 instances.

        Yields:
            DeviceOCSFModel objects representing device inventory events
        """
        self.log("Starting asset collection process...", level="info")
        self.log(f"Data path: {self._data_path.absolute()}", level="debug")

        try:
            # Set the checkpoint date at the start of collection
            new_most_recent_date = datetime.now().replace(tzinfo=pytz.UTC).isoformat()
            asset_count = 0

            for aws_devices in self.get_aws_devices():
                for aws_device in aws_devices:
                    try:
                        # Create product and metadata
                        product = Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION)
                        metadata = Metadata(product=product, version=self.OCSF_VERSION)

                        # Create OCSF device inventory event
                        device_ocsf = DeviceOCSFModel(
                            activity_id=2,
                            activity_name="Collect",
                            category_name="Discovery",
                            category_uid=5,
                            class_name="Device Inventory Info",
                            class_uid=5001,
                            type_name="Device Inventory Info: Collect",
                            severity="Informational",
                            severity_id=1,
                            type_uid=500102,
                            time=aws_device.date.timestamp(),
                            metadata=metadata,
                            device=aws_device.device,
                        )

                        asset_count += 1
                        yield device_ocsf

                    except Exception as e:
                        self.log(
                            f"Failed to create OCSF event for device {aws_device.device.uid}: {str(e)}", level="error"
                        )
                        self.log_exception(e)
                        continue

            # Update checkpoint with the new date
            self.new_most_recent_date = new_most_recent_date
            self.log(f"Asset collection completed. Generated {asset_count} device inventory events", level="info")

        except Exception as e:
            self.log(f"Error during asset collection: {str(e)}", level="error")
            self.log_exception(e)
            raise
