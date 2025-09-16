import pytest
from unittest import mock
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.module import Module
from dateutil.parser import isoparse

from asset_connector.users_assets import AwsUsersAssetConnector, AwsUser


@pytest.fixture
def test_aws_users_asset_connector(symphony_storage):
    module = Module()
    module.configuration = {
        "aws_access_key": "fakeKey",
        "aws_secret_access_key": "fakeSecret",
        "aws_region_name": "eu-north-1",
    }
    aws_users_connector = AwsUsersAssetConnector(module=module, data_path=symphony_storage)
    aws_users_connector.configuration = {
        "sekoia_base_url": "https://test.sekoia.io",
        "sekoia_api_key": "fakeApiKey",
        "frequency": 60,
    }
    aws_users_connector.log = mock.Mock()
    aws_users_connector.log_exception = mock.Mock()

    yield aws_users_connector


def get_paginator_side_effect(operation_name):
    mock_paginator = mock.MagicMock()
    if operation_name == "list_users":
        mock_paginator.paginate.return_value = [
            {
                "Users": [
                    {
                        "UserName": "testuser",
                        "UserId": "AID1234567890EXAMPLE",
                        "Arn": "arn:aws:iam::123456789012:user/testuser",
                        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                        "PasswordLastUsed": isoparse("2023-10-10T12:00:00Z"),
                        "Tags": [{"Key": "Name", "Value": "Test User"}],
                    }
                ]
            }
        ]
    elif operation_name == "list_groups_for_user":
        mock_paginator.paginate.return_value = [
            {
                "Groups": [
                    {
                        "GroupName": "testgroup",
                        "GroupId": "AGP1234567890EXAMPLE",
                        "Arn": "arn:aws:iam::123456789012:group/testgroup",
                        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                        "Tags": [{"Key": "Name", "Value": "Test Group"}],
                    }
                ]
            }
        ]
    return mock_paginator


def test_get_assets(test_aws_users_asset_connector):
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = get_paginator_side_effect
    mock_client.list_mfa_devices.return_value = {
        "MFADevices": [
            {
                "UserName": "testuser",
                "SerialNumber": "arn:aws:iam::123456789012:mfa/testuser",
                "EnableDate": isoparse("2023-10-05T12:00:00Z"),
            }
        ]
    }
    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
    asset = test_aws_users_asset_connector.get_assets().__next__()
    assert isinstance(asset, UserOCSFModel)
    assert asset.user.name == "testuser"
    # assert asset.user.uid == "arn:aws:iam::123456789012:user/testuser"
    assert len(asset.user.groups) == 1
    assert asset.user.has_mfa == True
    assert asset.activity_id == 2
    assert asset.metadata.product.name == "AWS IAM"


def test_update_checkpoint_success(test_aws_users_asset_connector):
    """Test successful checkpoint update with valid date."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_users_asset_connector.new_most_recent_date = test_date

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        test_aws_users_asset_connector.update_checkpoint()

    # Verify the cache was updated with the correct date
    mock_cache.__setitem__.assert_called_once_with("most_recent_date_seen", test_date)

    # Verify logging was called
    test_aws_users_asset_connector.log.assert_called_with(f"Checkpoint updated with date: {test_date}", level="info")


def test_update_checkpoint_with_none_date(test_aws_users_asset_connector):
    """Test checkpoint update when new_most_recent_date is None."""
    test_aws_users_asset_connector.new_most_recent_date = None

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        test_aws_users_asset_connector.update_checkpoint()

    # Verify the cache was not updated
    mock_cache.__setitem__.assert_not_called()

    # Verify warning was logged
    test_aws_users_asset_connector.log.assert_called_with(
        "Warning: new_most_recent_date is None, skipping checkpoint update", level="warning"
    )


def test_update_checkpoint_with_empty_string(test_aws_users_asset_connector):
    """Test checkpoint update with empty string date."""
    test_aws_users_asset_connector.new_most_recent_date = ""

    # Mock the entire context object
    mock_context = mock.MagicMock()
    mock_cache = mock.MagicMock()
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        test_aws_users_asset_connector.update_checkpoint()

    # Verify the cache was updated with empty string
    mock_cache.__setitem__.assert_called_once_with("most_recent_date_seen", "")

    # Verify logging was called
    test_aws_users_asset_connector.log.assert_called_with("Checkpoint updated with date: ", level="info")


def test_update_checkpoint_exception_handling(test_aws_users_asset_connector):
    """Test checkpoint update when an exception occurs during cache write."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_users_asset_connector.new_most_recent_date = test_date

    # Mock the context to raise an exception
    mock_context = mock.MagicMock()
    mock_context.__enter__.side_effect = Exception("Cache write failed")

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        test_aws_users_asset_connector.update_checkpoint()

    # Verify error logging was called
    test_aws_users_asset_connector.log.assert_called_with(
        "Failed to update checkpoint: Cache write failed", level="error"
    )

    # Verify log_exception was called
    test_aws_users_asset_connector.log_exception.assert_called_once()


def test_update_checkpoint_integration(test_aws_users_asset_connector):
    """Test checkpoint update integration with actual context storage."""
    test_date = "2023-10-15T12:00:00Z"
    test_aws_users_asset_connector.new_most_recent_date = test_date

    # Call update_checkpoint
    test_aws_users_asset_connector.update_checkpoint()

    # Verify the date was stored in context
    assert test_aws_users_asset_connector.most_recent_date_seen == test_date

    # Verify logging was called
    test_aws_users_asset_connector.log.assert_called_with(f"Checkpoint updated with date: {test_date}", level="info")
