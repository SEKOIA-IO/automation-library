from microsoft_ad.base import MicrosoftADModule, MicrosoftADAction
from microsoft_ad.user import ResetUserPasswordAction, EnableUserAction, DisableUserAction

from unittest.mock import patch


def configured_action(action: MicrosoftADAction):
    module = MicrosoftADModule()
    a = action(module)

    a.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password"
    }

    return a


def test_disable_user():
    action = configured_action(DisableUserAction)
    response = True

    with patch("microsoft_ad.base.MicrosoftADAction.search_userdn_query", return_value="test_ad"):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            
            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_enable_user():
    action = configured_action(EnableUserAction)
    response = True

    with patch("microsoft_ad.base.MicrosoftADAction.search_userdn_query", return_value="test_ad"):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            
            results = action.run({"username": "test_username", "basedn": "cn=test_basedn"})

            assert results is None


def test_reset_password_user():
    action = configured_action(ResetUserPasswordAction)
    response = True

    with patch("microsoft_ad.base.MicrosoftADAction.search_userdn_query", return_value="test_ad"):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            
            results = action.run({"username": "test_username", "basedn": "cn=test_basedn", "new_password" : "test_new_password"})

            assert results is None