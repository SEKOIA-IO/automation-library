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
