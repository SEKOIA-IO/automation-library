from unittest.mock import Mock, patch

import pytest
from ldap3.core.exceptions import LDAPException

from microsoft_ad.actions_base import MicrosoftADAction, MicrosoftADModule


class ConcreteMicrosoftADAction(MicrosoftADAction):
    def run(self, arguments):
        pass


class TestSearchUserdnQuery:
    def test_search_returns_empty_list_when_no_users_found(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert result == []
        assert action.log.call_count >= 2

    def test_search_returns_user_with_dn_and_account_control(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=Test User,OU=Users,DC=example,DC=com",
                "attributes": {"cn": "Test User", "mail": "test@example.com", "userAccountControl": 512},
            }
        ]
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert len(result) == 1
        assert result[0][0] == "CN=Test User,OU=Users,DC=example,DC=com"
        assert result[0][1] == 512

    def test_search_handles_account_control_as_list(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=Test User,DC=example,DC=com",
                "attributes": {"cn": "Test User", "userAccountControl": [514]},
            }
        ]
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert result[0][1] == 514

    def test_search_handles_empty_account_control_list(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=Test User,DC=example,DC=com",
                "attributes": {"cn": "Test User", "userAccountControl": []},
            }
        ]
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert result[0][1] is None

    def test_search_ignores_non_search_entries(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {"type": "searchResRef", "uri": "ldap://other.example.com"},
            {
                "type": "searchResEntry",
                "dn": "CN=Valid User,DC=example,DC=com",
                "attributes": {"cn": "Valid User", "userAccountControl": 512},
            },
        ]
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert len(result) == 1

    def test_search_ignores_entries_without_cn(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=No CN User,DC=example,DC=com",
                "attributes": {"userAccountControl": 512},
            }
        ]
        action.client = mock_client

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert result == []

    def test_search_raises_exception_on_ldap_error(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.search.side_effect = Exception("Connection timeout")
        action.client = mock_client

        with pytest.raises(Exception) as exc_info:
            action.search_userdn_query("testuser", "DC=example,DC=com")

        assert "LDAP search failed" in str(exc_info.value)
        assert "Connection timeout" in str(exc_info.value)

    def test_search_builds_correct_filter(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        action.search_userdn_query("test.test", "DC=test,DC=com")

        assert mock_client.search.call_count >= 1
        first_call_kwargs = mock_client.search.call_args_list[0]
        assert first_call_kwargs[1]["search_base"] == "DC=test,DC=com"
        assert "samaccountname=test.test" in first_call_kwargs[1]["search_filter"]

    def test_search_builds_filter_with_email(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        action.search_userdn_query("test.test", "DC=test,DC=com", email="test@example.com")

        assert mock_client.search.call_count >= 1
        first_call_kwargs = mock_client.search.call_args_list[0]
        search_filter = first_call_kwargs[1]["search_filter"]
        assert search_filter.startswith("(&")
        assert "(mail=test@example.com)" in search_filter
        assert "(|(samaccountname=test.test)" in search_filter

    def test_search_builds_filter_with_email_only(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        action.search_userdn_query(None, "DC=test,DC=com", email="test.integration@integration.local")

        assert mock_client.search.call_count >= 1
        first_call_kwargs = mock_client.search.call_args_list[0]
        search_filter = first_call_kwargs[1]["search_filter"]
        assert search_filter == "(mail=test.integration@integration.local)"

    def test_search_raises_when_no_username_and_no_email(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        with pytest.raises(ValueError, match="At least one of"):
            action.search_userdn_query(None, "DC=test,DC=com")

    def test_search_builds_filter_without_email(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        action.search_userdn_query("test.test", "DC=test,DC=com", email=None)

        assert mock_client.search.call_count >= 1
        first_call_kwargs = mock_client.search.call_args_list[0]
        search_filter = first_call_kwargs[1]["search_filter"]
        assert search_filter.startswith("(|")
        assert not search_filter.startswith("(&")

    def test_search_returns_multiple_users(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=User One,DC=example,DC=com",
                "attributes": {"cn": "User One", "userAccountControl": 512},
            },
            {
                "type": "searchResEntry",
                "dn": "CN=User Two,DC=example,DC=com",
                "attributes": {"cn": "User Two", "userAccountControl": 514},
            },
        ]
        action.client = mock_client

        result = action.search_userdn_query("user", "DC=example,DC=com")

        assert len(result) == 2

    def test_search_uses_shared_client(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.client = mock_client

        action.search_userdn_query("testuser", "DC=example,DC=com")

        assert mock_client.search.call_count >= 1

    def test_client_property_uses_default_and_override(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.module = MicrosoftADModule()
        action.module.configuration = {
            "servername": "test_servername",
            "admin_username": "test_admin_username",
            "admin_password": "test_admin_password",
        }

        default_client = Mock()
        with (
            patch("microsoft_ad.actions_base.Server") as mock_server,
            patch(
                "microsoft_ad.actions_base.Connection",
                return_value=default_client,
            ),
        ):
            assert action.client is default_client
            assert action.client is default_client
            mock_server.assert_called_once_with(host="test_servername", port=636, use_ssl=True)

        override_client = Mock()
        action.client = override_client
        assert action.client is override_client
        assert action.client_for(None) is override_client

    def test_client_for_specific_host(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.module = MicrosoftADModule()
        action.module.configuration = {
            "servername": "test_servername",
            "admin_username": "test_admin_username",
            "admin_password": "test_admin_password",
        }

        created_client = Mock()
        with (
            patch("microsoft_ad.actions_base.Server") as mock_server,
            patch(
                "microsoft_ad.actions_base.Connection",
                return_value=created_client,
            ) as mock_connection,
        ):
            result = action.client_for("child.lab.test.com")

        assert result is created_client
        mock_server.assert_called_once_with(host="child.lab.test.com", port=636, use_ssl=True)
        mock_connection.assert_called_once_with(
            mock_server.return_value,
            auto_bind=True,
            user="test_admin_username",
            password="test_admin_password",
        )

    def test_get_forest_root_dn_and_child_domains(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        root_client = Mock()
        root_client.response = [
            {
                "type": "searchResEntry",
                "attributes": {"rootDomainNamingContext": ["DC=lab,DC=test,DC=com"]},
            }
        ]
        assert action._get_forest_root_dn(client=root_client) == "DC=lab,DC=test,DC=com"

        root_client.response = [
            {
                "type": "searchResEntry",
                "attributes": {"rootDomainNamingContext": "DC=lab,DC=test,DC=com"},
            }
        ]
        assert action._get_forest_root_dn(client=root_client) == "DC=lab,DC=test,DC=com"

        child_client = Mock()
        child_client.response = [
            {
                "type": "searchResEntry",
                "attributes": {"nCName": ["DC=child,DC=lab,DC=test,DC=com"]},
            },
            {
                "type": "searchResEntry",
                "attributes": {"nCName": "DC=lab,DC=test,DC=com"},
            },
        ]
        assert action._get_child_domains("DC=lab,DC=test,DC=com", client=child_client) == [
            "DC=child,DC=lab,DC=test,DC=com"
        ]

    def test_get_forest_root_dn_and_child_domains_handle_ldap_errors(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        failing_client = Mock()
        failing_client.search.side_effect = LDAPException("boom")

        assert action._get_forest_root_dn(client=failing_client) is None
        assert action._get_child_domains("DC=lab,DC=test,DC=com", client=failing_client) == []
