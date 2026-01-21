import pytest
from unittest.mock import Mock
from microsoft_ad.actions_base import MicrosoftADAction


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

        action.search_userdn_query("john.doe", "DC=test,DC=com")

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args
        assert call_kwargs[1]["search_base"] == "DC=test,DC=com"
        assert "samaccountname=john.doe" in call_kwargs[1]["search_filter"]

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
