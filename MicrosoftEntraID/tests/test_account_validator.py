from unittest.mock import AsyncMock, Mock, patch

import pytest
from sekoia_automation.module import Module

from azure_ad.account_validator import AzureADAccountValidator


@pytest.fixture
def test_azure_ad_account_validator(symphony_storage):
    module = Module()
    module_configuration: dict = {
        "tenant_id": "fake_tenant_id",
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
    }
    module.configuration = module_configuration

    validator = AzureADAccountValidator(module=module, data_path=symphony_storage)
    validator.error = Mock()

    yield validator


def _mock_per_user_checks_ok(validator: AzureADAccountValidator) -> None:
    """Patch all per-user check methods to succeed."""
    validator._check_user_member_of = AsyncMock()
    validator._check_user_admin_roles = AsyncMock()
    validator._check_user_auth_methods = AsyncMock()


def test_configuration(test_azure_ad_account_validator):
    """Test that the validator has the correct configuration."""
    assert test_azure_ad_account_validator.module.configuration["tenant_id"] == "fake_tenant_id"
    assert test_azure_ad_account_validator.module.configuration["client_id"] == "fake_client_id"
    assert test_azure_ad_account_validator.module.configuration["client_secret"] == "fake_client_secret"


# ---------------------------------------------------------------------------
# validate() — integration with the event loop
# ---------------------------------------------------------------------------


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_all_checks_pass(mock_get_event_loop, test_azure_ad_account_validator):
    """validate() returns True when _run_all_checks succeeds."""
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop
    mock_loop.run_until_complete.return_value = True

    result = test_azure_ad_account_validator.validate()

    assert result is True
    mock_loop.run_until_complete.assert_called_once()
    test_azure_ad_account_validator.error.assert_not_called()


@patch("azure_ad.account_validator.asyncio.get_event_loop")
def test_validate_fatal_connection_error(mock_get_event_loop, test_azure_ad_account_validator):
    """validate() returns False and logs an error when the event loop raises."""
    mock_loop = Mock()
    mock_get_event_loop.return_value = mock_loop
    mock_loop.run_until_complete.side_effect = Exception("Connection failed")

    result = test_azure_ad_account_validator.validate()

    assert result is False
    test_azure_ad_account_validator.error.assert_called_once_with(
        "Impossible to connect to the Azure AD tenant: Connection failed"
    )


# ---------------------------------------------------------------------------
# _run_all_checks() — step 1: list users with signInActivity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_all_checks_all_pass(test_azure_ad_account_validator):
    """Returns True when listing users succeeds and all per-user checks pass."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="user-id-1")
    _mock_per_user_checks_ok(test_azure_ad_account_validator)

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is True
    test_azure_ad_account_validator.error.assert_not_called()


@pytest.mark.asyncio
async def test_run_all_checks_list_users_fails(test_azure_ad_account_validator):
    """Returns False immediately with one error when listing users (step 1) fails."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(side_effect=Exception("Insufficient privileges"))
    _mock_per_user_checks_ok(test_azure_ad_account_validator)

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is False
    assert test_azure_ad_account_validator.error.call_count == 1
    error_msg = test_azure_ad_account_validator.error.call_args[0][0]
    assert "User.Read.All" in error_msg
    assert "AuditLog.Read.All" in error_msg
    assert "Insufficient privileges" in error_msg


@pytest.mark.asyncio
async def test_run_all_checks_no_users_in_tenant(test_azure_ad_account_validator):
    """Returns True without running per-user checks when the tenant has no users."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value=None)
    _mock_per_user_checks_ok(test_azure_ad_account_validator)

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is True
    test_azure_ad_account_validator.error.assert_not_called()
    # Per-user checks must NOT be called when there is no user ID
    test_azure_ad_account_validator._check_user_member_of.assert_not_called()
    test_azure_ad_account_validator._check_user_admin_roles.assert_not_called()
    test_azure_ad_account_validator._check_user_auth_methods.assert_not_called()


# ---------------------------------------------------------------------------
# _run_all_checks() — step 2: per-user permission checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_all_checks_member_of_fails(test_azure_ad_account_validator):
    """Returns False and logs an error when the memberOf check fails."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="user-id-1")
    _mock_per_user_checks_ok(test_azure_ad_account_validator)
    test_azure_ad_account_validator._check_user_member_of = AsyncMock(side_effect=Exception("Access denied"))

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is False
    assert test_azure_ad_account_validator.error.call_count == 1
    error_msg = test_azure_ad_account_validator.error.call_args[0][0]
    assert "Directory.Read.All" in error_msg
    assert "Access denied" in error_msg


@pytest.mark.asyncio
async def test_run_all_checks_admin_roles_fails(test_azure_ad_account_validator):
    """Returns False and logs an error when the admin roles check fails."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="user-id-1")
    _mock_per_user_checks_ok(test_azure_ad_account_validator)
    test_azure_ad_account_validator._check_user_admin_roles = AsyncMock(side_effect=Exception("Forbidden"))

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is False
    assert test_azure_ad_account_validator.error.call_count == 1
    error_msg = test_azure_ad_account_validator.error.call_args[0][0]
    assert "Directory.Read.All" in error_msg
    assert "Forbidden" in error_msg


@pytest.mark.asyncio
async def test_run_all_checks_auth_methods_fails(test_azure_ad_account_validator):
    """Returns False and logs an error when the auth methods check fails."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="user-id-1")
    _mock_per_user_checks_ok(test_azure_ad_account_validator)
    test_azure_ad_account_validator._check_user_auth_methods = AsyncMock(
        side_effect=Exception("UserAuthenticationMethod.Read.All missing")
    )

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is False
    assert test_azure_ad_account_validator.error.call_count == 1
    error_msg = test_azure_ad_account_validator.error.call_args[0][0]
    assert "UserAuthenticationMethod.Read.All" in error_msg


@pytest.mark.asyncio
async def test_run_all_checks_all_per_user_fail(test_azure_ad_account_validator):
    """Returns False and logs one error per failing per-user check."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="user-id-1")
    error = Exception("Unauthorized")
    test_azure_ad_account_validator._check_user_member_of = AsyncMock(side_effect=error)
    test_azure_ad_account_validator._check_user_admin_roles = AsyncMock(side_effect=error)
    test_azure_ad_account_validator._check_user_auth_methods = AsyncMock(side_effect=error)

    result = await test_azure_ad_account_validator._run_all_checks()

    assert result is False
    assert test_azure_ad_account_validator.error.call_count == 3


@pytest.mark.asyncio
async def test_run_all_checks_per_user_checks_use_returned_user_id(test_azure_ad_account_validator):
    """Per-user checks are called with the user ID returned by _check_list_users."""
    test_azure_ad_account_validator._check_list_users = AsyncMock(return_value="specific-user-id")
    _mock_per_user_checks_ok(test_azure_ad_account_validator)

    await test_azure_ad_account_validator._run_all_checks()

    test_azure_ad_account_validator._check_user_member_of.assert_called_once_with("specific-user-id")
    test_azure_ad_account_validator._check_user_admin_roles.assert_called_once_with("specific-user-id")
    test_azure_ad_account_validator._check_user_auth_methods.assert_called_once_with("specific-user-id")
