from microsoft_ad.base import MicrosoftADModule, MicrosoftADAction
from microsoft_ad.user import (
    ResetUserPasswordAction,
    EnableUserAction,
    DisableUserAction,
)

from unittest.mock import patch
import pytest


def configured_action(action: MicrosoftADAction):
    module = MicrosoftADModule()
    a = action(module)

    a.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password",
    }

    return a


@pytest.fixture
def one_user_dn():
    return [["CN=integration_test,CN=Users,DC=lab,DC=test,DC=com", 512]]


@pytest.fixture
def two_users_dn():
    return [
        ["CN=integration_test,CN=Users,DC=lab,DC=test,DC=com", 512],
        ["CN=integration test1,CN=Users,DC=lab,DC=test,DC=com", 514],
    ]


def test_disable_user(one_user_dn):
    action = configured_action(DisableUserAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_disable_two_users(two_users_dn):
    action = configured_action(DisableUserAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "success"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})


def test_enable_user(one_user_dn):
    action = configured_action(EnableUserAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_enable_two_users(two_users_dn):
    action = configured_action(EnableUserAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "success"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})


def test_reset_password_user(one_user_dn):
    action = configured_action(ResetUserPasswordAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "new_password": "test_new_password",
                }
            )

            assert results is None


def test_reset_password_two_users(two_users_dn):
    action = configured_action(ResetUserPasswordAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "success"

                results = action.run(
                    {
                        "username": "test_username",
                        "basedn": "cn=test_basedn",
                        "new_password": "test_new_password",
                    }
                )


def test_unsuccess_query(one_user_dn):
    action = configured_action(DisableUserAction)
    response = True

    with patch(
        "microsoft_ad.base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "insufficientAccessRights"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

                assert results is None
