from datetime import datetime
from unittest import mock

import pytest
import pytz
from botocore.exceptions import ClientError, NoCredentialsError
from dateutil.parser import isoparse
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
from sekoia_automation.module import Module

from asset_connector.device_assets import AwsDevice, AwsDeviceAssetConnector
from connectors import AwsModule, AwsModuleConfiguration


@pytest.fixture
def test_aws_device_asset_connector(symphony_storage):
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key="fakeKey",
        aws_secret_access_key="fakeSecret",
        aws_region_name="eu-north-1",
    )
    aws_device_connector = AwsDeviceAssetConnector(module=module, data_path=symphony_storage)
    aws_device_connector.configuration = {
        "sekoia_base_url": "https://test.sekoia.io",
        "sekoia_api_key": "fakeApiKey",
        "frequency": 60,
    }
    aws_device_connector.log = mock.Mock()
    aws_device_connector.log_exception = mock.Mock()

    yield aws_device_connector


def test_get_device_os(test_aws_device_asset_connector):
    windows = OperatingSystem(name="Windows", type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS)
    linux = OperatingSystem(name="Linux", type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
    macos = OperatingSystem(name="MacOS", type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
    unknown = OperatingSystem(name="Unknown", type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

    # Test Windows detection
    assert test_aws_device_asset_connector.get_device_os("Windows Server 2019") == windows
    assert test_aws_device_asset_connector.get_device_os("windows") == windows

    # Test Linux detection
    assert test_aws_device_asset_connector.get_device_os("Linux Ubuntu") == linux
    assert test_aws_device_asset_connector.get_device_os("linux") == linux
    assert test_aws_device_asset_connector.get_device_os("UNIX") == linux

    # Test macOS detection
    assert test_aws_device_asset_connector.get_device_os("MacOS Big Sur") == macos
    assert test_aws_device_asset_connector.get_device_os("mac") == macos

    # Test unknown platforms
    assert test_aws_device_asset_connector.get_device_os("") == unknown
    assert test_aws_device_asset_connector.get_device_os(None) == unknown
    assert test_aws_device_asset_connector.get_device_os("Solaris") == OperatingSystem(
        name="Solaris", type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN
    )


def test_extract_network_interfaces(test_aws_device_asset_connector):
    """Test network interface extraction from EC2 instance data."""
    interfaces_data = [
        {
            "NetworkInterfaceId": "eni-0c2dee0a44bced651",
            "Description": "Primary network interface",
            "MacAddress": "06:f5:34:c6:b9:a3",
            "PrivateIpAddress": "172.31.30.218",
            "PrivateDnsName": "ip-172-31-30-218.eu-north-1.compute.internal",
        },
        {
            "NetworkInterfaceId": "eni-1234567890abcdef0",
            "Description": "Secondary network interface",
            "MacAddress": "06:f5:34:c6:b9:a4",
            "PrivateIpAddress": "172.31.30.219",
            "PrivateDnsName": "ip-172-31-30-219.eu-north-1.compute.internal",
        },
    ]

    result = test_aws_device_asset_connector._extract_network_interfaces(interfaces_data)

    assert len(result) == 2
    assert isinstance(result[0], NetworkInterface)
    assert result[0].uid == "eni-0c2dee0a44bced651"
    assert result[0].name == "Primary network interface"
    assert result[0].mac == "06:f5:34:c6:b9:a3"
    assert result[0].ip == "172.31.30.218"
    assert result[0].hostname == "ip-172-31-30-218.eu-north-1.compute.internal"
    assert result[0].type == NetworkInterfaceTypeStr.WIRED
    assert result[0].type_id == NetworkInterfaceTypeId.WIRED
    assert result[1].uid == "eni-1234567890abcdef0"


def test_extract_network_interfaces_empty(test_aws_device_asset_connector):
    """Test network interface extraction with empty list."""
    result = test_aws_device_asset_connector._extract_network_interfaces([])
    assert result == []


def test_extract_network_interfaces_with_error(test_aws_device_asset_connector):
    """Test network interface extraction when one interface has invalid data."""
    interfaces_data = [
        {
            "NetworkInterfaceId": "eni-valid",
            "MacAddress": "06:f5:34:c6:b9:a3",
            "PrivateIpAddress": "172.31.30.218",
        },
        {
            # This will cause an error if NetworkInterface requires certain fields
        },
    ]

    result = test_aws_device_asset_connector._extract_network_interfaces(interfaces_data)

    # Should have at least the valid interface
    assert len(result) >= 1
    assert result[0].uid == "eni-valid"


def test_extract_security_groups(test_aws_device_asset_connector):
    """Test security group extraction from EC2 instance data."""
    security_groups_data = [
        {
            "GroupId": "sg-09b53a8472dbf6457",
            "GroupName": "launch-wizard-1",
        },
        {
            "GroupId": "sg-1234567890abcdef0",
            "GroupName": "default",
        },
    ]

    result = test_aws_device_asset_connector._extract_security_groups(security_groups_data)

    assert len(result) == 2
    assert isinstance(result[0], Group)
    assert result[0].uid == "sg-09b53a8472dbf6457"
    assert result[0].name == "launch-wizard-1"
    assert result[1].uid == "sg-1234567890abcdef0"
    assert result[1].name == "default"


def test_extract_security_groups_empty(test_aws_device_asset_connector):
    """Test security group extraction with empty list."""
    result = test_aws_device_asset_connector._extract_security_groups([])
    assert result == []


def test_extract_security_groups_with_error(test_aws_device_asset_connector):
    """Test security group extraction when one group has invalid data."""
    security_groups_data = [
        {
            "GroupId": "sg-valid",
            "GroupName": "valid-group",
        },
        {
            # Invalid data
        },
    ]

    result = test_aws_device_asset_connector._extract_security_groups(security_groups_data)

    # Should have at least the valid group
    assert len(result) >= 1
    assert result[0].uid == "sg-valid"


def test_extract_name_from_tags(test_aws_device_asset_connector):
    """Test extraction of Name tag from EC2 instance tags."""
    tags = [
        {"Key": "Environment", "Value": "Production"},
        {"Key": "Name", "Value": "UbuntuInstance"},
        {"Key": "Owner", "Value": "admin"},
    ]

    result = test_aws_device_asset_connector._extract_name_from_tags(tags)
    assert result == "UbuntuInstance"


def test_extract_name_from_tags_no_name(test_aws_device_asset_connector):
    """Test extraction of Name tag when it doesn't exist."""
    tags = [
        {"Key": "Environment", "Value": "Production"},
        {"Key": "Owner", "Value": "admin"},
    ]

    result = test_aws_device_asset_connector._extract_name_from_tags(tags)
    assert result is None


def test_extract_name_from_tags_empty(test_aws_device_asset_connector):
    """Test extraction of Name tag from empty list."""
    result = test_aws_device_asset_connector._extract_name_from_tags([])
    assert result is None


def test_extract_autoscale_group_from_tags(test_aws_device_asset_connector):
    """Test extraction of autoscaling group name from EC2 instance tags."""
    tags = [
        {"Key": "Name", "Value": "WebServer"},
        {"Key": "aws:autoscaling:groupName", "Value": "web-server-asg"},
        {"Key": "Environment", "Value": "Production"},
    ]

    result = test_aws_device_asset_connector._extract_autoscale_group_from_tags(tags)
    assert result == "web-server-asg"


def test_extract_autoscale_group_from_tags_no_asg(test_aws_device_asset_connector):
    """Test extraction of autoscaling group when it doesn't exist."""
    tags = [
        {"Key": "Name", "Value": "WebServer"},
        {"Key": "Environment", "Value": "Production"},
    ]

    result = test_aws_device_asset_connector._extract_autoscale_group_from_tags(tags)
    assert result is None


def test_extract_autoscale_group_from_tags_empty(test_aws_device_asset_connector):
    """Test extraction of autoscaling group from empty list."""
    result = test_aws_device_asset_connector._extract_autoscale_group_from_tags([])
    assert result is None


def test_extract_organization_from_owner_id(test_aws_device_asset_connector):
    """Test extraction of organization from AWS Owner ID (account ID)."""
    owner_id = "516755368338"

    result = test_aws_device_asset_connector._extract_organization_from_owner_id(owner_id)

    assert result is not None
    assert result.uid == "516755368338"
    assert result.name == "AWS Account 516755368338"
    assert result.ou_name is None
    assert result.ou_uid is None


def test_extract_organization_from_owner_id_none(test_aws_device_asset_connector):
    """Test extraction of organization when owner ID is None."""
    result = test_aws_device_asset_connector._extract_organization_from_owner_id(None)
    assert result is None


def test_extract_organization_from_owner_id_empty(test_aws_device_asset_connector):
    """Test extraction of organization when owner ID is empty string."""
    result = test_aws_device_asset_connector._extract_organization_from_owner_id("")
    assert result is None


def test_extract_organization_from_owner_id_short_account(test_aws_device_asset_connector):
    """Test extraction of organization with shorter account ID."""
    owner_id = "123456789012"

    result = test_aws_device_asset_connector._extract_organization_from_owner_id(owner_id)

    assert result is not None
    assert result.uid == "123456789012"
    assert result.name == "AWS Account 123456789012"


def test_extract_organization_from_owner_id_whitespace(test_aws_device_asset_connector):
    """Test extraction of organization when owner ID has whitespace."""
    owner_id = "  516755368338  "

    result = test_aws_device_asset_connector._extract_organization_from_owner_id(owner_id)

    assert result is not None
    assert result.uid == "  516755368338  "
    assert result.name == "AWS Account   516755368338  "


def test_extract_organization_from_owner_id_invalid(test_aws_device_asset_connector):
    """Test extraction of organization with invalid owner ID format."""
    # Test that the function handles unexpected formats gracefully
    owner_id = "invalid-format-123"

    result = test_aws_device_asset_connector._extract_organization_from_owner_id(owner_id)

    # Should still create an organization object even with non-standard format
    assert result is not None
    assert result.uid == "invalid-format-123"
    assert result.name == "AWS Account invalid-format-123"


def test_client_success(test_aws_device_asset_connector):
    """Test successful AWS client creation."""
    with mock.patch("boto3.Session") as mock_session:
        mock_client = mock.MagicMock()
        mock_session_instance = mock.MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance

        result = test_aws_device_asset_connector.client()

        mock_session.assert_called_once_with(
            aws_access_key_id="fakeKey", aws_secret_access_key="fakeSecret", region_name="eu-north-1"
        )
        mock_session_instance.client.assert_called_once_with("ec2")
        assert result == mock_client


def test_client_no_credentials_error(test_aws_device_asset_connector):
    """Test client creation with no credentials."""
    with mock.patch("boto3.Session") as mock_session:
        mock_session.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            test_aws_device_asset_connector.client()

        test_aws_device_asset_connector.log.assert_called_with("AWS credentials not found or invalid", level="error")
        test_aws_device_asset_connector.log_exception.assert_called_once()


def test_client_general_exception(test_aws_device_asset_connector):
    """Test client creation with general exception."""
    with mock.patch("boto3.Session") as mock_session:
        mock_session.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            test_aws_device_asset_connector.client()

        test_aws_device_asset_connector.log.assert_called_with(
            "Failed to create AWS client: Connection failed", level="error"
        )
        test_aws_device_asset_connector.log_exception.assert_called_once()


def test_most_recent_date_seen_success(test_aws_device_asset_connector):
    """Test successful retrieval of most_recent_date_seen from checkpoint."""
    test_date = "2023-10-15T12:00:00Z"

    # Mock the context
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_cache.get.return_value = test_date
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        result = test_aws_device_asset_connector.most_recent_date_seen

    assert result == test_date
    mock_cache.get.assert_called_once_with("most_recent_date_seen")


def test_most_recent_date_seen_none(test_aws_device_asset_connector):
    """Test most_recent_date_seen when checkpoint value is None."""
    # Mock the context
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_cache.get.return_value = None
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        result = test_aws_device_asset_connector.most_recent_date_seen

    assert result is None


def test_most_recent_date_seen_non_string(test_aws_device_asset_connector):
    """Test most_recent_date_seen when checkpoint value is not a string."""
    # Mock the context
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_cache.get.return_value = 12345  # Non-string value
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        result = test_aws_device_asset_connector.most_recent_date_seen

    assert result == "12345"  # Should be converted to string


def test_most_recent_date_seen_exception(test_aws_device_asset_connector):
    """Test most_recent_date_seen when an exception occurs."""
    # Mock the context to raise an exception
    mock_context = mock.MagicMock()
    mock_context.__enter__.side_effect = Exception("Storage error")

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        result = test_aws_device_asset_connector.most_recent_date_seen

    assert result is None
    test_aws_device_asset_connector.log.assert_called_with(
        "Failed to retrieve checkpoint: Storage error", level="error"
    )
    test_aws_device_asset_connector.log_exception.assert_called_once()


def test_extract_device_from_instance_success(test_aws_device_asset_connector):
    """Test successful device extraction from AWS instance."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
        "State": {"Name": "running"},
        "Tags": [{"Key": "Name", "Value": "TestInstance"}],
        "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
        "BlockDeviceMappings": [
            {
                "Ebs": {
                    "AttachTime": isoparse("2023-10-01T12:00:00Z"),
                    "DeleteOnTermination": True,
                    "Status": "attached",
                    "VolumeId": "vol-049df61146c4d7901",
                }
            }
        ],
    }
    owner_id = "516755368338"

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None, owner_id)

    assert isinstance(result, AwsDevice)
    assert result.device.uid == "i-1234567890abcdef0"
    assert result.device.hostname == "ec2-203-0-113-25.compute-1.amazonaws.com"
    assert result.device.os.name == "Linux"
    assert result.device.type == DeviceTypeStr.SERVER
    assert result.device.org is not None
    assert result.device.org.uid == "516755368338"
    assert result.device.org.name == "AWS Account 516755368338"


def test_extract_device_from_instance_no_instance_id(test_aws_device_asset_connector):
    """Test device extraction when instance has no InstanceId."""
    instance_data = {
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert result is None
    test_aws_device_asset_connector.log.assert_called_with("Instance missing InstanceId, skipping", level="warning")


def test_extract_device_from_instance_no_creation_time(test_aws_device_asset_connector):
    """Test device extraction when instance has no creation time."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert result is None
    test_aws_device_asset_connector.log.assert_called_with(
        "Instance i-1234567890abcdef0 has no creation time, skipping", level="warning"
    )


def test_extract_device_from_instance_with_launch_time(test_aws_device_asset_connector):
    """Test device extraction using LaunchTime when no EBS attachment time."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Windows Server 2019",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
        "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert isinstance(result, AwsDevice)
    assert result.device.uid == "i-1234567890abcdef0"
    assert result.device.os.name == "Windows"
    assert result.date == isoparse("2023-10-01T12:00:00Z")


def test_extract_device_from_instance_with_private_dns(test_aws_device_asset_connector):
    """Test device extraction using PrivateDnsName when no PublicDnsName."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
        "PrivateDnsName": "ip-10-0-1-1.ec2.internal",
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert isinstance(result, AwsDevice)
    assert result.device.hostname == "ip-10-0-1-1.ec2.internal"


def test_extract_device_from_instance_with_instance_id_hostname(test_aws_device_asset_connector):
    """Test device extraction using InstanceId as hostname when no DNS names."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert isinstance(result, AwsDevice)
    assert result.device.hostname == "i-1234567890abcdef0"


def test_extract_device_from_instance_with_date_filter(test_aws_device_asset_connector):
    """Test device extraction with date filter excluding older instances."""
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
    }

    # Date filter is after the instance launch time
    date_filter = isoparse("2023-10-02T12:00:00Z")
    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, date_filter)

    assert result is None


def test_extract_device_from_instance_timezone_handling(test_aws_device_asset_connector):
    """Test device extraction with timezone handling."""
    # Create datetime without timezone
    naive_datetime = datetime(2023, 10, 1, 12, 0, 0)
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "PlatformDetails": "Linux/UNIX",
        "LaunchTime": naive_datetime,
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert isinstance(result, AwsDevice)
    # The date should be converted to UTC
    assert result.date.tzinfo == pytz.UTC


def test_extract_device_from_instance_exception_handling(test_aws_device_asset_connector):
    """Test device extraction with exception handling."""
    # Create instance data that will cause an exception
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "LaunchTime": "invalid_date",  # This will cause an exception during parsing
    }

    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)

    assert result is None
    # Verify that an error was logged (error message may vary depending on parsing implementation)
    assert test_aws_device_asset_connector.log.call_count > 0
    # Check that error logging was called with level='error' and contains the instance ID
    error_calls = [
        call
        for call in test_aws_device_asset_connector.log.call_args_list
        if len(call[1]) > 0 and call[1].get("level") == "error"
    ]
    assert len(error_calls) > 0
    assert "i-1234567890abcdef0" in str(error_calls[0])
    test_aws_device_asset_connector.log_exception.assert_called_once()


def test_get_aws_devices_success(test_aws_device_asset_connector):
    """Test successful AWS devices collection."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "State": {"Name": "running"},
                            "Tags": [{"Key": "Name", "Value": "TestInstance"}],
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                            "BlockDeviceMappings": [
                                {
                                    "Ebs": {
                                        "AttachTime": isoparse("2023-10-01T12:00:00Z"),
                                        "DeleteOnTermination": True,
                                        "Status": "attached",
                                        "VolumeId": "vol-049df61146c4d7901",
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    devices = list(test_aws_device_asset_connector.get_aws_devices())

    assert len(devices) == 1
    device_list = devices[0]
    assert isinstance(device_list, list)
    assert len(device_list) == 1

    device = device_list[0]
    assert isinstance(device, AwsDevice)
    assert device.device.uid == "i-1234567890abcdef0"
    assert device.device.hostname == "ec2-203-0-113-25.compute-1.amazonaws.com"
    assert device.device.os.name == "Linux"
    assert device.device.os.type == OSTypeStr.LINUX
    assert device.device.os.type_id == OSTypeId.LINUX
    assert device.device.type == DeviceTypeStr.SERVER
    assert device.device.type_id == DeviceTypeId.SERVER

    # Verify device count logging
    test_aws_device_asset_connector.log.assert_any_call("Successfully collected 1 AWS devices", level="info")


def test_get_aws_devices_with_checkpoint(test_aws_device_asset_connector):
    """Test AWS devices collection with checkpoint date filter."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-02T12:00:00Z"),  # After checkpoint
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    # Mock checkpoint date by patching the context
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_cache.get.return_value = "2023-10-01T12:00:00Z"
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        devices = list(test_aws_device_asset_connector.get_aws_devices())

    assert len(devices) == 1
    assert len(devices[0]) == 1


def test_get_aws_devices_with_invalid_checkpoint(test_aws_device_asset_connector):
    """Test AWS devices collection with invalid checkpoint date."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    # Mock invalid checkpoint date by patching the context
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_cache.get.return_value = "invalid-date"
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        devices = list(test_aws_device_asset_connector.get_aws_devices())

    # Should still work, just ignore the invalid checkpoint
    # The test verifies that invalid checkpoint dates are handled gracefully
    assert len(devices) == 1


def test_get_aws_devices_empty_response(test_aws_device_asset_connector):
    """Test AWS devices collection with empty response."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = []
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    devices = list(test_aws_device_asset_connector.get_aws_devices())

    assert len(devices) == 0
    test_aws_device_asset_connector.log.assert_called_with("Successfully collected 0 AWS devices", level="info")


def test_get_aws_devices_client_error(test_aws_device_asset_connector):
    """Test AWS devices collection with ClientError."""
    mock_client = mock.MagicMock()
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}}
    mock_client.get_paginator.return_value.paginate.side_effect = ClientError(error_response, "DescribeInstances")
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(ClientError):
        list(test_aws_device_asset_connector.get_aws_devices())

    test_aws_device_asset_connector.log.assert_called_with(
        "AWS API error (UnauthorizedOperation): An error occurred (UnauthorizedOperation) when calling the DescribeInstances operation: Access denied",
        level="error",
    )


def test_get_aws_devices_instance_processing_error(test_aws_device_asset_connector):
    """Test AWS devices collection when individual instance processing fails."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                        },
                        {
                            "InstanceId": "i-invalid",  # This will cause processing to fail
                            "LaunchTime": "invalid_date",
                        },
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    devices = list(test_aws_device_asset_connector.get_aws_devices())

    # Should still process the valid instance
    assert len(devices) == 1
    assert len(devices[0]) == 1
    assert devices[0][0].device.uid == "i-1234567890abcdef0"

    # Verify error was logged for invalid instance (error message may vary)
    error_calls = [
        call
        for call in test_aws_device_asset_connector.log.call_args_list
        if len(call[1]) > 0 and call[1].get("level") == "error"
    ]
    assert len(error_calls) > 0
    assert "i-invalid" in str(error_calls[0])

    # Verify device count logging shows only 1 valid device
    test_aws_device_asset_connector.log.assert_any_call("Successfully collected 1 AWS devices", level="info")

    # The invalid instance should be skipped but not cause the entire process to fail
    # This test verifies the error handling works without breaking the overall flow


def test_get_assets_success(test_aws_device_asset_connector):
    """Test successful asset collection."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "State": {"Name": "running"},
                            "Tags": [{"Key": "Name", "Value": "TestInstance"}],
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                            "BlockDeviceMappings": [
                                {
                                    "Ebs": {
                                        "AttachTime": isoparse("2023-10-01T12:00:00Z"),
                                        "DeleteOnTermination": True,
                                        "Status": "attached",
                                        "VolumeId": "vol-049df61146c4d7901",
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    assets = list(test_aws_device_asset_connector.get_assets())

    assert len(assets) == 1
    asset = assets[0]
    assert isinstance(asset, DeviceOCSFModel)
    assert asset.device.uid == "i-1234567890abcdef0"
    assert asset.device.hostname == "ec2-203-0-113-25.compute-1.amazonaws.com"
    assert asset.device.os.name == "Linux"
    assert asset.device.os.type == OSTypeStr.LINUX
    assert asset.device.os.type_id == OSTypeId.LINUX
    assert asset.device.type == DeviceTypeStr.SERVER
    assert asset.device.type_id == DeviceTypeId.SERVER
    assert asset.activity_id == 2
    assert asset.activity_name == "Collect"
    assert asset.category_name == "Discovery"
    assert asset.category_uid == 5
    assert asset.class_name == "Device Inventory Info"
    assert asset.class_uid == 5001
    assert asset.type_name == "Device Inventory Info: Collect"
    assert asset.severity == "Informational"
    assert asset.severity_id == 1
    assert asset.type_uid == 500102
    assert asset.metadata.product.name == "AWS EC2"
    assert asset.metadata.product.version == "N/A"
    assert asset.metadata.version == "1.6.0"

    # Verify checkpoint was updated
    assert test_aws_device_asset_connector.new_most_recent_date is not None


def test_get_assets_multiple_devices(test_aws_device_asset_connector):
    """Test asset collection with multiple devices."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "PublicDnsName": "ec2-1.compute-1.amazonaws.com",
                        },
                        {
                            "InstanceId": "i-9876543210fedcba0",
                            "InstanceType": "t3.small",
                            "PlatformDetails": "Windows Server 2019",
                            "LaunchTime": isoparse("2023-10-02T12:00:00Z"),
                            "PublicDnsName": "ec2-2.compute-1.amazonaws.com",
                        },
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    assets = list(test_aws_device_asset_connector.get_assets())

    assert len(assets) == 2
    assert assets[0].device.uid == "i-1234567890abcdef0"
    assert assets[0].device.os.name == "Linux"
    assert assets[1].device.uid == "i-9876543210fedcba0"
    assert assets[1].device.os.name == "Windows"


def test_get_assets_empty_devices(test_aws_device_asset_connector):
    """Test asset collection with no devices."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = []
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    assets = list(test_aws_device_asset_connector.get_assets())

    assert len(assets) == 0
    test_aws_device_asset_connector.log.assert_called_with(
        "Asset collection completed. Generated 0 device inventory events", level="info"
    )


def test_get_assets_device_processing_error(test_aws_device_asset_connector):
    """Test asset collection when device processing fails."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    # Mock _extract_device_from_instance to raise an exception
    with mock.patch.object(
        test_aws_device_asset_connector, "_extract_device_from_instance", side_effect=Exception("Processing error")
    ):
        assets = list(test_aws_device_asset_connector.get_assets())

    assert len(assets) == 0
    # The test verifies that when device processing fails, no assets are returned
    # and the process continues without crashing


def test_get_assets_ocsf_creation_error(test_aws_device_asset_connector):
    """Test asset collection when OCSF event creation fails."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.return_value.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "PlatformDetails": "Linux/UNIX",
                            "LaunchTime": isoparse("2023-10-01T12:00:00Z"),
                            "PublicDnsName": "ec2-203-0-113-25.compute-1.amazonaws.com",
                        }
                    ]
                }
            ]
        }
    ]
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)

    # Mock DeviceOCSFModel to raise an exception
    with mock.patch("asset_connector.device_assets.DeviceOCSFModel", side_effect=Exception("OCSF creation error")):
        assets = list(test_aws_device_asset_connector.get_assets())

    assert len(assets) == 0
    # The test verifies that when OCSF event creation fails, no assets are returned
    # and the process continues without crashing


def test_get_assets_exception_handling(test_aws_device_asset_connector):
    """Test asset collection with general exception handling."""
    # Mock get_aws_devices to raise an exception
    with mock.patch.object(test_aws_device_asset_connector, "get_aws_devices", side_effect=Exception("General error")):
        with pytest.raises(Exception, match="General error"):
            list(test_aws_device_asset_connector.get_assets())

    test_aws_device_asset_connector.log.assert_called_with(
        "Error during asset collection: General error", level="error"
    )


def test_aws_device_initialization():
    """Test AwsDevice class initialization."""
    device = Device(
        uid="i-1234567890abcdef0",
        hostname="test-host",
        os=OperatingSystem(name="Linux", type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX),
        type=DeviceTypeStr.SERVER,
        type_id=DeviceTypeId.SERVER,
    )
    date = datetime.now(pytz.UTC)

    aws_device = AwsDevice(device=device, date=date)

    assert aws_device.device == device
    assert aws_device.date == date


def test_aws_device_asset_connector_initialization(test_aws_device_asset_connector):
    """Test AwsDeviceAssetConnector initialization."""
    assert test_aws_device_asset_connector.PRODUCT_NAME == "AWS EC2"
    assert test_aws_device_asset_connector.OCSF_VERSION == "1.6.0"
    assert test_aws_device_asset_connector.PRODUCT_VERSION == "N/A"
    assert test_aws_device_asset_connector.new_most_recent_date is None
    assert hasattr(test_aws_device_asset_connector, "context")


def test_update_checkpoint_success(test_aws_device_asset_connector):
    """Test successful checkpoint update with valid date."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_device_asset_connector.new_most_recent_date = test_date

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        test_aws_device_asset_connector.update_checkpoint()

    # Verify the cache was updated with the correct date
    mock_cache.__setitem__.assert_called_once_with("most_recent_date_seen", test_date)

    # Verify logging was called
    test_aws_device_asset_connector.log.assert_called_with(f"Checkpoint updated with date: {test_date}", level="info")


def test_update_checkpoint_with_none_date(test_aws_device_asset_connector):
    """Test checkpoint update when new_most_recent_date is None."""
    test_aws_device_asset_connector.new_most_recent_date = None

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        test_aws_device_asset_connector.update_checkpoint()

    # Verify the cache was not updated
    mock_cache.__setitem__.assert_not_called()

    # Verify warning was logged
    test_aws_device_asset_connector.log.assert_called_with(
        "Warning: new_most_recent_date is None, skipping checkpoint update", level="warning"
    )


def test_update_checkpoint_with_empty_string(test_aws_device_asset_connector):
    """Test checkpoint update with empty string date."""
    test_aws_device_asset_connector.new_most_recent_date = ""

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        test_aws_device_asset_connector.update_checkpoint()

    # Verify the cache was updated with empty string
    mock_cache.__setitem__.assert_called_once_with("most_recent_date_seen", "")

    # Verify logging was called
    test_aws_device_asset_connector.log.assert_called_with("Checkpoint updated with date: ", level="info")


def test_update_checkpoint_exception_handling(test_aws_device_asset_connector):
    """Test checkpoint update when an exception occurs during cache write."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_device_asset_connector.new_most_recent_date = test_date

    # Mock the context to raise an exception
    mock_context = mock.MagicMock()
    mock_context.__enter__.side_effect = Exception("Cache write failed")

    with mock.patch.object(test_aws_device_asset_connector, "context", mock_context):
        test_aws_device_asset_connector.update_checkpoint()

    # Verify error logging was called
    test_aws_device_asset_connector.log.assert_called_with(
        "Failed to update checkpoint: Cache write failed", level="error"
    )

    # Verify log_exception was called
    test_aws_device_asset_connector.log_exception.assert_called_once()


def test_update_checkpoint_integration(test_aws_device_asset_connector):
    """Test checkpoint update integration with actual context storage."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_device_asset_connector.new_most_recent_date = test_date

    # Call update_checkpoint
    test_aws_device_asset_connector.update_checkpoint()

    # Verify the date was stored in context
    assert test_aws_device_asset_connector.most_recent_date_seen == test_date

    # Verify logging was called
    test_aws_device_asset_connector.log.assert_called_with(f"Checkpoint updated with date: {test_date}", level="info")
