from search_in_ad_modules.base import MicrosoftADModule, MicrosoftADAction
from search_in_ad_modules.search import SearchAction
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

def test_search():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    action = configured_action(SearchAction)
    results = action.run({"search_filter": search, "basedn": basedn})
    assert results is not None
