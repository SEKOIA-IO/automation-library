from microsoft_ad.base import MicrosoftADModule, MicrosoftADAction
from microsoft_ad.search import SearchAction
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


def test_search_no_attributes():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    action = configured_action(SearchAction)
    response = True

    with patch(
        "microsoft_ad.search.SearchAction.run",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"search_filter": search, "basedn": basedn})

            assert results is not None


def test_search_with_attributes():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    attributes = ["name"]

    action = configured_action(SearchAction)
    response = True

    with patch(
        "microsoft_ad.search.SearchAction.run",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"search_filter": search, "basedn": basedn, "attributes": attributes})

            assert results is not None


def test_search_in_base_exception():

    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    attributes = ["name"]
    action = configured_action(SearchAction)

    with patch("microsoft_ad.search.SearchAction.run", side_effect=Exception("mocked error")):
        with pytest.raises(Exception) as exc_info:
            action.run({"search_filter": search, "basedn": basedn, "attributes": attributes})

        # Verify the exception message
        assert str(exc_info.value) == f"Failed to search in this base {basedn}"
