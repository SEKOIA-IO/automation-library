import pytest
from unittest import mock
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.module import Module
from dateutil.parser import isoparse
from botocore.exceptions import NoCredentialsError, ClientError, BotoCoreError

from connectors import AwsModule, AwsModuleConfiguration
from asset_connector.users_assets import AwsUsersAssetConnector, AwsUser


@pytest.fixture
def test_aws_users_asset_connector(symphony_storage):
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key="fakeKey",
        aws_secret_access_key="fakeSecret",
        aws_region_name="eu-north-1",
    )
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
    elif operation_name == "list_attached_group_policies":
        mock_paginator.paginate.return_value = [
            {
                "AttachedPolicies": [
                    {
                        "PolicyName": "ReadOnlyAccess",
                        "PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess",
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


# Test AwsUser class
def test_aws_user_initialization():
    """Test AwsUser class initialization."""
    from sekoia_automation.asset_connector.models.ocsf.user import User, Account, AccountTypeStr, AccountTypeId
    from datetime import datetime

    # Create a test user
    account = Account(
        name="testuser",
        type=AccountTypeStr.AWS_ACCOUNT,
        type_id=AccountTypeId.AWS_ACCOUNT,
        uid="arn:aws:iam::123456789012:user/testuser",
    )
    user = User(name="testuser", uid="arn:aws:iam::123456789012:user/testuser", account=account)
    date = datetime.now()

    aws_user = AwsUser(user=user, date=date)

    assert aws_user.user == user
    assert aws_user.date == date


# Test client method
def test_client_success(test_aws_users_asset_connector):
    """Test successful client creation."""
    with mock.patch("boto3.Session") as mock_session:
        mock_client = mock.MagicMock()
        mock_session.return_value.client.return_value = mock_client

        result = test_aws_users_asset_connector.client()

        assert result == mock_client
        mock_session.assert_called_once_with(
            aws_access_key_id="fakeKey", aws_secret_access_key="fakeSecret", region_name="eu-north-1"
        )
        mock_session.return_value.client.assert_called_once_with("iam")


def test_client_no_credentials_error(test_aws_users_asset_connector):
    """Test client creation with NoCredentialsError."""
    with mock.patch("boto3.Session") as mock_session:
        mock_session.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            test_aws_users_asset_connector.client()

        test_aws_users_asset_connector.log.assert_called_with("AWS credentials not found or invalid", level="error")
        test_aws_users_asset_connector.log_exception.assert_called_once()


def test_client_general_exception(test_aws_users_asset_connector):
    """Test client creation with general exception."""
    with mock.patch("boto3.Session") as mock_session:
        mock_session.side_effect = Exception("General error")

        with pytest.raises(Exception):
            test_aws_users_asset_connector.client()

        test_aws_users_asset_connector.log.assert_called_with(
            "Failed to create AWS client: General error", level="error"
        )
        test_aws_users_asset_connector.log_exception.assert_called_once()


def test_extract_organization_from_arn_success(test_aws_users_asset_connector):
    """Test successful extraction of organization from ARN."""
    arn = "arn:aws:iam::123456789012:user/testuser"

    org = test_aws_users_asset_connector._extract_organization_from_arn(arn)

    assert org is not None
    assert org.uid == "123456789012"
    assert org.name == "AWS Account 123456789012"


def test_extract_organization_from_arn_empty(test_aws_users_asset_connector):
    """Test organization extraction with empty ARN."""
    org = test_aws_users_asset_connector._extract_organization_from_arn("")
    assert org is None


def test_extract_organization_from_arn_none(test_aws_users_asset_connector):
    """Test organization extraction with None ARN."""
    org = test_aws_users_asset_connector._extract_organization_from_arn(None)
    assert org is None


def test_extract_organization_from_arn_invalid_format(test_aws_users_asset_connector):
    """Test organization extraction with invalid ARN format."""
    invalid_arn = "invalid:arn:format"

    org = test_aws_users_asset_connector._extract_organization_from_arn(invalid_arn)

    # Should return None for invalid format (not enough parts)
    assert org is None


def test_extract_organization_from_arn_different_service(test_aws_users_asset_connector):
    """Test organization extraction from ARN of different AWS service."""
    arn = "arn:aws:s3::123456789012:bucket/mybucket"

    org = test_aws_users_asset_connector._extract_organization_from_arn(arn)

    assert org is not None
    assert org.uid == "123456789012"


def test_extract_organization_from_arn_no_account_id(test_aws_users_asset_connector):
    """Test organization extraction when account ID is empty."""
    arn = "arn:aws:iam:::user/testuser"

    org = test_aws_users_asset_connector._extract_organization_from_arn(arn)

    # Should return None when account ID is empty
    assert org is None


# Test most_recent_date_seen property
def test_most_recent_date_seen_success(test_aws_users_asset_connector):
    """Test successful retrieval of most_recent_date_seen."""
    test_date = "2023-10-15T12:00:00Z"

    mock_context = mock.MagicMock()
    mock_cache = {"most_recent_date_seen": test_date}
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        result = test_aws_users_asset_connector.most_recent_date_seen

    assert result == test_date


def test_most_recent_date_seen_none(test_aws_users_asset_connector):
    """Test most_recent_date_seen when value is None."""
    mock_context = mock.MagicMock()
    mock_cache = {"most_recent_date_seen": None}
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        result = test_aws_users_asset_connector.most_recent_date_seen

    assert result is None


def test_most_recent_date_seen_non_string(test_aws_users_asset_connector):
    """Test most_recent_date_seen when value is not a string."""
    mock_context = mock.MagicMock()
    mock_cache = {"most_recent_date_seen": 12345}
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        result = test_aws_users_asset_connector.most_recent_date_seen

    assert result == "12345"


def test_most_recent_date_seen_exception(test_aws_users_asset_connector):
    """Test most_recent_date_seen when exception occurs."""
    mock_context = mock.MagicMock()
    mock_context.__enter__.side_effect = Exception("Cache read failed")

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        result = test_aws_users_asset_connector.most_recent_date_seen

    assert result is None
    test_aws_users_asset_connector.log.assert_called_with(
        "Failed to retrieve checkpoint: Cache read failed", level="error"
    )
    test_aws_users_asset_connector.log_exception.assert_called_once()


# Test group_privileges method
def test_group_privileges_success(test_aws_users_asset_connector):
    """Test successful group privileges retrieval."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    mock_paginator.paginate.return_value = [
        {
            "AttachedPolicies": [
                {"PolicyName": "AdminAccess", "PolicyArn": "arn:aws:iam::aws:policy/AdminAccess"},
                {"PolicyName": "ReadOnlyAccess", "PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"},
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    policies = test_aws_users_asset_connector.group_privileges("testgroup")

    assert len(policies) == 2
    assert "AdminAccess" in policies
    assert "ReadOnlyAccess" in policies


def test_group_privileges_empty_group_name(test_aws_users_asset_connector):
    """Test group_privileges with empty group name."""
    policies = test_aws_users_asset_connector.group_privileges("")

    assert policies == []
    test_aws_users_asset_connector.log.assert_called_with(
        "Empty group name provided, returning False for admin status", level="warning"
    )


def test_group_privileges_client_error(test_aws_users_asset_connector):
    """Test group_privileges with ClientError."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        operation_name="ListAttachedGroupPolicies",
    )

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(ClientError):
        test_aws_users_asset_connector.group_privileges("testgroup")


def test_user_has_admin_policy_true(test_aws_users_asset_connector):
    """Test user_has_admin_policy returns True for admin user."""
    from sekoia_automation.asset_connector.models.ocsf.user import Group

    groups = [
        Group(name="testgroup", uid="arn:aws:iam::123456789012:group/testgroup", privileges=["AdminAccess"])
    ]

    is_admin = test_aws_users_asset_connector.user_has_admin_policy(groups)

    assert is_admin is True


def test_user_has_admin_policy_false(test_aws_users_asset_connector):
    """Test user_has_admin_policy returns False for non-admin user."""
    from sekoia_automation.asset_connector.models.ocsf.user import Group

    groups = [
        Group(name="testgroup", uid="arn:aws:iam::123456789012:group/testgroup", privileges=["ReadOnlyAccess"])
    ]

    is_admin = test_aws_users_asset_connector.user_has_admin_policy(groups)

    assert is_admin is False


def test_user_has_admin_policy_administrator(test_aws_users_asset_connector):
    """Test user_has_admin_policy recognizes 'administrator' pattern."""
    from sekoia_automation.asset_connector.models.ocsf.user import Group

    groups = [
        Group(
            name="testgroup",
            uid="arn:aws:iam::123456789012:group/testgroup",
            privileges=["AdministratorAccess"],
        )
    ]

    is_admin = test_aws_users_asset_connector.user_has_admin_policy(groups)

    assert is_admin is True


def test_user_has_admin_policy_poweruser(test_aws_users_asset_connector):
    """Test user_has_admin_policy recognizes 'poweruser' pattern."""
    from sekoia_automation.asset_connector.models.ocsf.user import Group

    groups = [
        Group(name="testgroup", uid="arn:aws:iam::123456789012:group/testgroup", privileges=["PowerUserAccess"])
    ]

    is_admin = test_aws_users_asset_connector.user_has_admin_policy(groups)

    assert is_admin is True


def test_user_has_admin_policy_empty_groups(test_aws_users_asset_connector):
    """Test user_has_admin_policy with empty groups list."""
    is_admin = test_aws_users_asset_connector.user_has_admin_policy([])

    assert is_admin is False


# Test get_groups_for_user method
def test_get_groups_for_user_success(test_aws_users_asset_connector):
    """Test successful group retrieval for a user."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    mock_paginator.paginate.return_value = [
        {
            "Groups": [
                {"GroupName": "testgroup1", "Arn": "arn:aws:iam::123456789012:group/testgroup1"},
                {"GroupName": "testgroup2", "Arn": "arn:aws:iam::123456789012:group/testgroup2"},
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
    test_aws_users_asset_connector.group_privileges = mock.MagicMock(return_value=["ReadOnlyAccess"])

    groups = test_aws_users_asset_connector.get_groups_for_user("testuser")

    assert len(groups) == 2
    assert groups[0].name == "testgroup1"
    assert groups[0].uid == "arn:aws:iam::123456789012:group/testgroup1"
    assert groups[0].privileges == ["ReadOnlyAccess"]
    assert groups[1].name == "testgroup2"
    assert groups[1].uid == "arn:aws:iam::123456789012:group/testgroup2"
    assert groups[1].privileges == ["ReadOnlyAccess"]


def test_get_groups_for_user_empty_user(test_aws_users_asset_connector):
    """Test get_groups_for_user with empty user name."""
    groups = test_aws_users_asset_connector.get_groups_for_user("")

    assert groups == []
    test_aws_users_asset_connector.log.assert_called_with(
        "Empty user name provided, returning empty groups list", level="warning"
    )


def test_get_groups_for_user_none_user(test_aws_users_asset_connector):
    """Test get_groups_for_user with None user name."""
    groups = test_aws_users_asset_connector.get_groups_for_user(None)

    assert groups == []
    test_aws_users_asset_connector.log.assert_called_with(
        "Empty user name provided, returning empty groups list", level="warning"
    )


def test_get_groups_for_user_client_error(test_aws_users_asset_connector):
    """Test get_groups_for_user with ClientError."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        operation_name="ListGroupsForUser",
    )

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(ClientError):
        test_aws_users_asset_connector.get_groups_for_user("testuser")

    test_aws_users_asset_connector.log.assert_called_with(
        "AWS API error fetching groups for user testuser (AccessDenied): An error occurred (AccessDenied) when calling the ListGroupsForUser operation: Access denied",
        level="error",
    )


def test_get_groups_for_user_boto_core_error(test_aws_users_asset_connector):
    """Test get_groups_for_user with BotoCoreError."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = BotoCoreError()

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(BotoCoreError):
        test_aws_users_asset_connector.get_groups_for_user("testuser")

    test_aws_users_asset_connector.log.assert_called_with(
        "Boto3 core error fetching groups for user testuser: An unspecified error occurred", level="error"
    )


def test_get_groups_for_user_processing_error(test_aws_users_asset_connector):
    """Test get_groups_for_user with group processing error."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    # Return a group with missing required fields to cause processing error
    mock_paginator.paginate.return_value = [
        {
            "Groups": [
                {
                    "GroupName": "testgroup",
                    # Missing Arn field
                }
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    groups = test_aws_users_asset_connector.get_groups_for_user("testuser")

    # Group class handles missing fields gracefully, so we get a group with empty uid
    assert len(groups) == 1
    assert groups[0].name == "testgroup"
    assert groups[0].uid == ""  # Empty due to missing Arn field


# Test get_mfa_status_for_user method
def test_get_mfa_status_for_user_success_with_mfa(test_aws_users_asset_connector):
    """Test successful MFA status check when user has MFA."""
    mock_client = mock.MagicMock()
    mock_client.list_mfa_devices.return_value = {
        "MFADevices": [{"UserName": "testuser", "SerialNumber": "arn:aws:iam::123456789012:mfa/testuser"}]
    }

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    has_mfa = test_aws_users_asset_connector.get_mfa_status_for_user("testuser")

    assert has_mfa is True


def test_get_mfa_status_for_user_success_without_mfa(test_aws_users_asset_connector):
    """Test successful MFA status check when user has no MFA."""
    mock_client = mock.MagicMock()
    mock_client.list_mfa_devices.return_value = {"MFADevices": []}

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    has_mfa = test_aws_users_asset_connector.get_mfa_status_for_user("testuser")

    assert has_mfa is False


def test_get_mfa_status_for_user_empty_user(test_aws_users_asset_connector):
    """Test get_mfa_status_for_user with empty user name."""
    has_mfa = test_aws_users_asset_connector.get_mfa_status_for_user("")

    assert has_mfa is False
    test_aws_users_asset_connector.log.assert_called_with(
        "Empty user name provided, returning False for MFA status", level="warning"
    )


def test_get_mfa_status_for_user_none_user(test_aws_users_asset_connector):
    """Test get_mfa_status_for_user with None user name."""
    has_mfa = test_aws_users_asset_connector.get_mfa_status_for_user(None)

    assert has_mfa is False
    test_aws_users_asset_connector.log.assert_called_with(
        "Empty user name provided, returning False for MFA status", level="warning"
    )


def test_get_mfa_status_for_user_client_error(test_aws_users_asset_connector):
    """Test get_mfa_status_for_user with ClientError."""
    mock_client = mock.MagicMock()
    mock_client.list_mfa_devices.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, operation_name="ListMFADevices"
    )

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(ClientError):
        test_aws_users_asset_connector.get_mfa_status_for_user("testuser")

    test_aws_users_asset_connector.log.assert_called_with(
        "AWS API error checking MFA for user testuser (AccessDenied): An error occurred (AccessDenied) when calling the ListMFADevices operation: Access denied",
        level="error",
    )


def test_get_mfa_status_for_user_boto_core_error(test_aws_users_asset_connector):
    """Test get_mfa_status_for_user with BotoCoreError."""
    mock_client = mock.MagicMock()
    mock_client.list_mfa_devices.side_effect = BotoCoreError()

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(BotoCoreError):
        test_aws_users_asset_connector.get_mfa_status_for_user("testuser")

    test_aws_users_asset_connector.log.assert_called_with(
        "Boto3 core error checking MFA for user testuser: An unspecified error occurred", level="error"
    )


# Test get_aws_users method
def test_get_aws_users_success(test_aws_users_asset_connector):
    """Test successful AWS users retrieval."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    mock_paginator.paginate.return_value = [
        {
            "Users": [
                {
                    "UserName": "testuser1",
                    "UserId": "AID1234567890EXAMPLE1",
                    "Arn": "arn:aws:iam::123456789012:user/testuser1",
                    "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                    "PasswordLastUsed": isoparse("2023-10-10T12:00:00Z"),
                },
                {
                    "UserName": "testuser2",
                    "UserId": "AID1234567890EXAMPLE2",
                    "Arn": "arn:aws:iam::123456789012:user/testuser2",
                    "CreateDate": isoparse("2023-10-02T12:00:00Z"),
                    "PasswordLastUsed": isoparse("2023-10-11T12:00:00Z"),
                },
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    users = list(test_aws_users_asset_connector.get_aws_users())

    assert len(users) == 1  # One batch of users
    assert len(users[0]) == 2  # Two users in the batch
    assert users[0][0].user.name == "testuser1"
    assert users[0][1].user.name == "testuser2"


def test_get_aws_users_with_date_filter(test_aws_users_asset_connector):
    """Test AWS users retrieval with date filtering."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    # Mock checkpoint date by mocking the context
    mock_context = mock.MagicMock()
    mock_cache = {"most_recent_date_seen": "2023-10-01T12:00:00Z"}
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        mock_paginator.paginate.return_value = [
            {
                "Users": [
                    {
                        "UserName": "testuser1",
                        "UserId": "AID1234567890EXAMPLE1",
                        "Arn": "arn:aws:iam::123456789012:user/testuser1",
                        "CreateDate": isoparse("2023-09-30T12:00:00Z"),  # Before filter date
                    },
                    {
                        "UserName": "testuser2",
                        "UserId": "AID1234567890EXAMPLE2",
                        "Arn": "arn:aws:iam::123456789012:user/testuser2",
                        "CreateDate": isoparse("2023-10-02T12:00:00Z"),  # After filter date
                    },
                ]
            }
        ]

        test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
        test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
        test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)

        users = list(test_aws_users_asset_connector.get_aws_users())

        # Only the second user should be included (after filter date)
        assert len(users) == 1
        assert len(users[0]) == 1
        assert users[0][0].user.name == "testuser2"


def test_get_aws_users_client_error(test_aws_users_asset_connector):
    """Test get_aws_users with ClientError."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, operation_name="ListUsers"
    )

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(ClientError):
        list(test_aws_users_asset_connector.get_aws_users())

    test_aws_users_asset_connector.log.assert_called_with(
        "AWS API error (AccessDenied): An error occurred (AccessDenied) when calling the ListUsers operation: Access denied",
        level="error",
    )


def test_get_aws_users_boto_core_error(test_aws_users_asset_connector):
    """Test get_aws_users with BotoCoreError."""
    mock_client = mock.MagicMock()
    mock_client.get_paginator.side_effect = BotoCoreError()

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)

    with pytest.raises(BotoCoreError):
        list(test_aws_users_asset_connector.get_aws_users())

    test_aws_users_asset_connector.log.assert_called_with(
        "Boto3 core error: An unspecified error occurred", level="error"
    )


def test_get_aws_users_invalid_date_format(test_aws_users_asset_connector):
    """Test get_aws_users with invalid date format in checkpoint."""
    # Mock checkpoint date by mocking the context
    mock_context = mock.MagicMock()
    mock_cache = {"most_recent_date_seen": "invalid-date"}
    mock_context.__enter__.return_value = mock_cache
    mock_context.__exit__.return_value = None

    with mock.patch.object(test_aws_users_asset_connector, "context", mock_context):
        mock_client = mock.MagicMock()
        mock_paginator = mock.MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "Users": [
                    {
                        "UserName": "testuser1",
                        "UserId": "AID1234567890EXAMPLE1",
                        "Arn": "arn:aws:iam::123456789012:user/testuser1",
                        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                    }
                ]
            }
        ]

        test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
        test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
        test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)

        users = list(test_aws_users_asset_connector.get_aws_users())

        # Should still work, just without date filtering
        assert len(users) == 1
        assert len(users[0]) == 1
        # Verify that the method handled the invalid date gracefully
        assert users[0][0].user.name == "testuser1"


# Test _extract_user_from_iam_user method
def test_extract_user_from_iam_user_success(test_aws_users_asset_connector):
    """Test successful user extraction from IAM user data."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
        "PasswordLastUsed": isoparse("2023-10-10T12:00:00Z"),
    }

    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is not None
    assert aws_user.user.name == "testuser"
    assert aws_user.user.uid == "arn:aws:iam::123456789012:user/testuser"
    assert aws_user.user.has_mfa is True
    assert aws_user.date == isoparse("2023-10-01T12:00:00Z")
    # Verify organization is extracted from ARN
    assert aws_user.user.org is not None
    assert aws_user.user.org.uid == "123456789012"
    assert aws_user.user.org.name == "AWS Account 123456789012"


def test_extract_user_from_iam_user_missing_username(test_aws_users_asset_connector):
    """Test user extraction with missing username."""
    user_data = {
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is None
    test_aws_users_asset_connector.log.assert_called_with("User missing UserName or Arn, skipping", level="warning")


def test_extract_user_from_iam_user_missing_arn(test_aws_users_asset_connector):
    """Test user extraction with missing ARN."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is None
    test_aws_users_asset_connector.log.assert_called_with("User missing UserName or Arn, skipping", level="warning")


def test_extract_user_from_iam_user_missing_create_date(test_aws_users_asset_connector):
    """Test user extraction with missing creation date."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
    }

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is None
    test_aws_users_asset_connector.log.assert_called_with(
        "User testuser has no creation time, skipping", level="warning"
    )


def test_extract_user_from_iam_user_with_date_filter(test_aws_users_asset_connector):
    """Test user extraction with date filter."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    # Date filter after user creation date
    date_filter = isoparse("2023-10-02T12:00:00Z")

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, date_filter)

    assert aws_user is None  # User should be filtered out


def test_extract_user_from_iam_user_groups_error(test_aws_users_asset_connector):
    """Test user extraction when groups fetching fails."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(side_effect=Exception("Groups error"))
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is not None
    assert aws_user.user.groups == []  # Should be empty due to error
    # Verify that the method was called and handled the error gracefully
    test_aws_users_asset_connector.get_groups_for_user.assert_called_once_with("testuser")


def test_extract_user_from_iam_user_mfa_error(test_aws_users_asset_connector):
    """Test user extraction when MFA checking fails."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(side_effect=Exception("MFA error"))
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

    assert aws_user is not None
    assert aws_user.user.has_mfa is False  # Should be False due to error
    # Verify that the method was called and handled the error gracefully
    test_aws_users_asset_connector.get_mfa_status_for_user.assert_called_once_with("testuser")


def test_extract_user_from_iam_user_general_error(test_aws_users_asset_connector):
    """Test user extraction with general error."""
    user_data = {
        "UserName": "testuser",
        "UserId": "AID1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:user/testuser",
        "CreateDate": isoparse("2023-10-01T12:00:00Z"),
    }

    # Mock the User class to raise an exception
    with mock.patch("asset_connector.users_assets.User") as mock_user_class:
        mock_user_class.side_effect = Exception("User creation error")

        aws_user = test_aws_users_asset_connector._extract_user_from_iam_user(user_data, None)

        assert aws_user is None
        test_aws_users_asset_connector.log.assert_called_with(
            "Error extracting user from IAM user testuser: User creation error", level="error"
        )


# Enhanced get_assets test
def test_get_assets_comprehensive(test_aws_users_asset_connector):
    """Test comprehensive get_assets functionality."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    mock_paginator.paginate.return_value = [
        {
            "Users": [
                {
                    "UserName": "testuser",
                    "UserId": "AID1234567890EXAMPLE",
                    "Arn": "arn:aws:iam::123456789012:user/testuser",
                    "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                    "PasswordLastUsed": isoparse("2023-10-10T12:00:00Z"),
                }
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    assets = list(test_aws_users_asset_connector.get_assets())

    assert len(assets) == 1
    asset = assets[0]

    assert isinstance(asset, UserOCSFModel)
    assert asset.user.name == "testuser"
    assert asset.user.uid == "arn:aws:iam::123456789012:user/testuser"
    assert asset.user.has_mfa is True
    assert asset.activity_id == 2
    assert asset.activity_name == "Collect"
    assert asset.category_name == "Discovery"
    assert asset.class_name == "User Inventory"
    assert asset.type_name == "User Inventory Info: Collect"
    assert asset.metadata.product.name == "AWS IAM"
    assert asset.metadata.version == "1.6.0"

    # Verify checkpoint was updated
    assert test_aws_users_asset_connector.new_most_recent_date is not None


def test_get_assets_with_exception(test_aws_users_asset_connector):
    """Test get_assets with exception during processing."""
    mock_client = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_client.get_paginator.return_value = mock_paginator

    mock_paginator.paginate.return_value = [
        {
            "Users": [
                {
                    "UserName": "testuser",
                    "UserId": "AID1234567890EXAMPLE",
                    "Arn": "arn:aws:iam::123456789012:user/testuser",
                    "CreateDate": isoparse("2023-10-01T12:00:00Z"),
                }
            ]
        }
    ]

    test_aws_users_asset_connector.client = mock.MagicMock(return_value=mock_client)
    test_aws_users_asset_connector.get_groups_for_user = mock.MagicMock(return_value=[])
    test_aws_users_asset_connector.get_mfa_status_for_user = mock.MagicMock(return_value=True)
    test_aws_users_asset_connector.user_has_admin_policy = mock.MagicMock(return_value=False)

    # Mock UserOCSFModel to raise an exception
    with mock.patch("asset_connector.users_assets.UserOCSFModel") as mock_ocsf:
        mock_ocsf.side_effect = Exception("OCSF creation error")

        assets = list(test_aws_users_asset_connector.get_assets())

        assert len(assets) == 0  # No assets due to error
        # Verify that the method handled the error gracefully and continued processing
        test_aws_users_asset_connector.get_groups_for_user.assert_called_once_with("testuser")
        test_aws_users_asset_connector.get_mfa_status_for_user.assert_called_once_with("testuser")
