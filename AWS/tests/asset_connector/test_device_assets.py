import pytest
from unittest import mock
from datetime import datetime
import pytz
from botocore.exceptions import ClientError, NoCredentialsError
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceOCSFModel,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
    DeviceTypeStr,
    DeviceTypeId,
)
from sekoia_automation.module import Module
from dateutil.parser import isoparse

from asset_connector.device_assets import AwsDeviceAssetConnector, AwsDevice


@pytest.fixture
def test_aws_device_asset_connector(symphony_storage):
    module = Module()
    module.configuration = {
        "aws_access_key": "fakeKey",
        "aws_secret_access_key": "fakeSecret",
        "aws_region_name": "eu-north-1",
    }
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
    assert test_aws_device_asset_connector.get_device_os("Solaris") == OperatingSystem(name="Solaris", type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)


def test_client_success(test_aws_device_asset_connector):
    """Test successful AWS client creation."""
    with mock.patch('boto3.Session') as mock_session:
        mock_client = mock.MagicMock()
        mock_session_instance = mock.MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance
        
        result = test_aws_device_asset_connector.client()
        
        mock_session.assert_called_once_with(
            aws_access_key_id="fakeKey",
            aws_secret_access_key="fakeSecret",
            region_name="eu-north-1"
        )
        mock_session_instance.client.assert_called_once_with("ec2")
        assert result == mock_client


def test_client_no_credentials_error(test_aws_device_asset_connector):
    """Test client creation with no credentials."""
    with mock.patch('boto3.Session') as mock_session:
        mock_session.side_effect = NoCredentialsError()
        
        with pytest.raises(NoCredentialsError):
            test_aws_device_asset_connector.client()
        
        test_aws_device_asset_connector.log.assert_called_with("AWS credentials not found or invalid", level="error")
        test_aws_device_asset_connector.log_exception.assert_called_once()


def test_client_general_exception(test_aws_device_asset_connector):
    """Test client creation with general exception."""
    with mock.patch('boto3.Session') as mock_session:
        mock_session.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            test_aws_device_asset_connector.client()
        
        test_aws_device_asset_connector.log.assert_called_with("Failed to create AWS client: Connection failed", level="error")
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
    test_aws_device_asset_connector.log.assert_called_with("Failed to retrieve checkpoint: Storage error", level="error")
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
    
    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)
    
    assert isinstance(result, AwsDevice)
    assert result.device.uid == "i-1234567890abcdef0"
    assert result.device.hostname == "ec2-203-0-113-25.compute-1.amazonaws.com"
    assert result.device.os.name == "Linux"
    assert result.device.type == DeviceTypeStr.SERVER


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
        "LaunchTime": "invalid_date",  # This will cause an exception
    }
    
    result = test_aws_device_asset_connector._extract_device_from_instance(instance_data, None)
    
    assert result is None
    # The actual error message includes the specific error details
    test_aws_device_asset_connector.log.assert_called_with(
        "Error extracting device from instance i-1234567890abcdef0: 'str' object has no attribute 'tzinfo'", level="error"
    )
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
    test_aws_device_asset_connector.log.assert_called_with(
        "Successfully collected 0 AWS devices", level="info"
    )


def test_get_aws_devices_client_error(test_aws_device_asset_connector):
    """Test AWS devices collection with ClientError."""
    mock_client = mock.MagicMock()
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}}
    mock_client.get_paginator.return_value.paginate.side_effect = ClientError(
        error_response, "DescribeInstances"
    )
    test_aws_device_asset_connector.client = mock.MagicMock(return_value=mock_client)
    
    with pytest.raises(ClientError):
        list(test_aws_device_asset_connector.get_aws_devices())
    
    test_aws_device_asset_connector.log.assert_called_with(
        "AWS API error (UnauthorizedOperation): An error occurred (UnauthorizedOperation) when calling the DescribeInstances operation: Access denied",
        level="error"
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
                        }
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
                        }
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
    with mock.patch.object(test_aws_device_asset_connector, '_extract_device_from_instance', side_effect=Exception("Processing error")):
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
    with mock.patch('asset_connector.device_assets.DeviceOCSFModel', side_effect=Exception("OCSF creation error")):
        assets = list(test_aws_device_asset_connector.get_assets())
    
    assert len(assets) == 0
    # The test verifies that when OCSF event creation fails, no assets are returned
    # and the process continues without crashing


def test_get_assets_exception_handling(test_aws_device_asset_connector):
    """Test asset collection with general exception handling."""
    # Mock get_aws_devices to raise an exception
    with mock.patch.object(test_aws_device_asset_connector, 'get_aws_devices', side_effect=Exception("General error")):
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
        type_id=DeviceTypeId.SERVER
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
    assert hasattr(test_aws_device_asset_connector, 'context')


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
