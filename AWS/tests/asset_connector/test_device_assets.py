import pytest
from unittest import mock
from sekoia_automation.asset_connector.models.ocsf.device import (
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

    assert test_aws_device_asset_connector.get_device_os("Windows Server 2019") == windows
    assert test_aws_device_asset_connector.get_device_os("Linux Ubuntu") == linux
    assert test_aws_device_asset_connector.get_device_os("MacOS Big Sur") == macos


def test_get_aws_devices(test_aws_device_asset_connector):
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
    devices = test_aws_device_asset_connector.get_aws_devices().__next__()
    assert isinstance(devices, list)
    for device in devices:
        assert isinstance(device, AwsDevice)
        assert device.device.uid == "i-1234567890abcdef0"
        assert device.device.hostname == "ec2-203-0-113-25.compute-1.amazonaws.com"
        assert device.device.os.name == "Linux"
        assert device.device.os.type == OSTypeStr.LINUX
        assert device.device.os.type_id == OSTypeId.LINUX
        assert device.device.type == DeviceTypeStr.SERVER
        assert device.device.type_id == DeviceTypeId.SERVER


def test_get_assets(test_aws_device_asset_connector):
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
    asset = test_aws_device_asset_connector.get_assets().__next__()
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
