from unittest.mock import Mock, patch

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

                action.run({"username": "test_username", "basedn": "cn=test_basedn"})


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

                action.run({"username": "test_username", "basedn": "cn=test_basedn"})


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

                action.run(
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
                    "email": "test@example.com",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "test@example.com")


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
                    "email": "test@example.com",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "test@example.com")


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
                    "email": "test@example.com",
                }
            )

            mock_search.assert_called_once_with("test_username", "cn=test_basedn", "test@example.com")


@pytest.mark.parametrize(
    "action_class,run_arguments",
    [
        (
            ResetUserPasswordAction,
            {"username": "test_username", "basedn": "cn=test_basedn", "new_password": "test_new_password"},
        ),
        (EnableUserAction, {"username": "test_username", "basedn": "cn=test_basedn"}),
        (DisableUserAction, {"username": "test_username", "basedn": "cn=test_basedn"}),
    ],
)
def test_actions_raise_when_user_not_found(action_class, run_arguments):
    action = configured_action(action_class)

    with patch("microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query", return_value=[]):
        with pytest.raises(Exception, match="User not found"):
            action.run(run_arguments)


def test_reset_password_raises_when_ldap_result_is_not_success():
    action = configured_action(ResetUserPasswordAction)
    mock_client = Mock()
    mock_client.extend.microsoft.modify_password.return_value = True
    mock_client.result.get.return_value = "insufficientAccessRights"

    with pytest.raises(Exception, match="Password reset failed"):
        action._reset_password_for_user(mock_client, "CN=test", "test_username", "test_new_password")


def test_enable_user_raises_when_ldap_result_is_not_success():
    action = configured_action(EnableUserAction)
    mock_client = Mock()
    mock_client.modify.return_value = True
    mock_client.result.get.return_value = "insufficientAccessRights"

    with pytest.raises(Exception, match="Enable action failed"):
        action._enable_user(mock_client, "CN=test", 512, "test_username")


def test_disable_user_raises_when_ldap_result_is_not_success():
    action = configured_action(DisableUserAction)
    mock_client = Mock()
    mock_client.modify.return_value = True
    mock_client.result.get.return_value = "insufficientAccessRights"

    with pytest.raises(Exception, match="Disable action failed"):
        action._disable_user(mock_client, "CN=test", 512, "test_username")


def test_disable_domain_controller_uses_shared_client(one_user_dn):
    action = configured_action(DisableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client_for") as mock_client_for:
            mock_client = Mock()
            mock_client_for.return_value = mock_client
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "domain_controller": "child.lab.test.com",
                }
            )

            mock_client_for.assert_called_once_with("child.lab.test.com")
            mock_search.assert_called_once_with("test_username", "cn=test_basedn", None)


def test_enable_domain_controller_uses_shared_client(one_user_dn):
    action = configured_action(EnableUserAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client_for") as mock_client_for:
            mock_client = Mock()
            mock_client_for.return_value = mock_client
            mock_client.modify.return_value = True
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "domain_controller": "child.lab.test.com",
                }
            )

            mock_client_for.assert_called_once_with("child.lab.test.com")
            mock_search.assert_called_once_with("test_username", "cn=test_basedn", None)


def test_reset_password_domain_controller_uses_shared_client(one_user_dn):
    action = configured_action(ResetUserPasswordAction)

    with patch(
        "microsoft_ad.actions_base.MicrosoftADAction.search_userdn_query",
        return_value=one_user_dn,
    ) as mock_search:
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client_for") as mock_client_for:
            mock_client = Mock()
            mock_client_for.return_value = mock_client
            mock_client.result.get.return_value = "success"

            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "new_password": "test_new_password",
                    "domain_controller": "child.lab.test.com",
                }
            )

            mock_client_for.assert_called_once_with("child.lab.test.com")
            mock_search.assert_called_once_with("test_username", "cn=test_basedn", None)


def test_domain_controller_connection_error_propagates(one_user_dn):
    action = configured_action(ResetUserPasswordAction)

    with patch("microsoft_ad.actions_base.MicrosoftADAction.client_for", side_effect=Exception("bad controller")):
        with pytest.raises(Exception, match="bad controller"):
            action.run(
                {
                    "username": "test_username",
                    "basedn": "cn=test_basedn",
                    "new_password": "test_new_password",
                    "domain_controller": "child.lab.test.com",
                }
            )


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
