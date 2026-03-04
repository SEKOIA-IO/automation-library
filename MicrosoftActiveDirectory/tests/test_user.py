from unittest.mock import call, patch

import pytest

from microsoft_ad.actions_base import MicrosoftADAction, MicrosoftADModule
from microsoft_ad.user_actions import DisableUserAction, EnableUserAction, ResetUserPasswordAction


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
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_disable_two_users(two_users_dn):
    action = configured_action(DisableUserAction)
    response = True

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "success"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})


def test_enable_user(one_user_dn):
    action = configured_action(EnableUserAction)
    response = True

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_enable_two_users(two_users_dn):
    action = configured_action(EnableUserAction)
    response = True

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "success"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})


def test_reset_password_user(one_user_dn):
    action = configured_action(ResetUserPasswordAction)
    response = True

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
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
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
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
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            with pytest.raises(Exception):
                mock_client.modify.return_value = response
                mock_client.result.get.return_value = "insufficientAccessRights"

                results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

                assert results is None


def test_disable_apply_to_all_success(two_users_dn):
    action = configured_action(DisableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn", "apply_to_all": True})

            assert results["total_found"] == 2
            assert results["total_success"] == 2
            assert results["total_failed"] == 0
            assert len(results["affected_users"]) == 2
            assert all(u["status"] == "success" for u in results["affected_users"])


def test_enable_apply_to_all_success(two_users_dn):
    action = configured_action(EnableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn", "apply_to_all": True})

            assert results["total_found"] == 2
            assert results["total_success"] == 2
            assert results["total_failed"] == 0


def test_reset_password_apply_to_all_success(two_users_dn):
    action = configured_action(ResetUserPasswordAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.result.get.return_value = "success"

            results = action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "new_password": "test_new_password",
                    "apply_to_all": True,
                }
            )

            assert results["total_found"] == 2
            assert results["total_success"] == 2
            assert results["total_failed"] == 0


def test_disable_apply_to_all_partial_failure(two_users_dn):
    action = configured_action(DisableUserAction)

    call_count = 0

    def modify_side_effect(dn, changes, controls):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        from ldap3.core.exceptions import LDAPException

        raise LDAPException("Connection lost")

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.side_effect = modify_side_effect
            mock_client.result.get.return_value = "success"

            results = action.run({"username": "test_username", "basedn": "cn=test_basedn", "apply_to_all": True})

            assert results["total_success"] == 1
            assert results["total_failed"] == 1
            failed = [u for u in results["affected_users"] if u["status"] == "failed"]
            assert len(failed) == 1
            assert "error" in failed[0]


def test_disable_apply_to_all_total_failure(two_users_dn):
    action = configured_action(DisableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            from ldap3.core.exceptions import LDAPException

            mock_client.modify.side_effect = LDAPException("Connection lost")

            with pytest.raises(Exception, match="All disable operations failed"):
                action.run({"username": "test_username", "basedn": "cn=test_basedn", "apply_to_all": True})


def test_disable_display_name_passed_to_search(one_user_dn):
    action = configured_action(DisableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "display_name": "Test User",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "Test User")


def test_enable_display_name_passed_to_search(one_user_dn):
    action = configured_action(EnableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "display_name": "Test User",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "Test User")


def test_reset_password_display_name_passed_to_search(one_user_dn):
    action = configured_action(ResetUserPasswordAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "new_password": "test_new_password",
                    "display_name": "Test User",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "Test User")


def test_enable_apply_to_all_total_failure(two_users_dn):
    action = configured_action(EnableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            from ldap3.core.exceptions import LDAPException

            mock_client.modify.side_effect = LDAPException("Connection lost")

            with pytest.raises(Exception, match="All enable operations failed"):
                action.run({"username": "test_username", "basedn": "cn=test_basedn", "apply_to_all": True})


def test_reset_password_apply_to_all_total_failure(two_users_dn):
    action = configured_action(ResetUserPasswordAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=two_users_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            from ldap3.core.exceptions import LDAPException

            mock_client.extend.microsoft.modify_password.side_effect = LDAPException("Connection lost")

            with pytest.raises(Exception, match="All password resets failed"):
                action.run(
                    {
                        "username": "test_username",
                        "basedn": "cn=test_basedn",
                        "new_password": "test_new_password",
                        "apply_to_all": True,
                    }
                )
