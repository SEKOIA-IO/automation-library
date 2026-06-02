import pytest
from unittest.mock import Mock, patch

from microsoft_ad.actions_base import MicrosoftADAction, MicrosoftADModule


class ConcreteMicrosoftADAction(MicrosoftADAction):
    """Concrete implementation for testing."""

    def run(self, arguments):
        pass


def configured_action():
    module = MicrosoftADModule()
    a = ConcreteMicrosoftADAction(module)

    a.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password",
    }

    return a


class TestMultiDomainSearch:
    """Tests for multi-domain search functionality in Red Forest environments."""

    def test_get_forest_root_dn_success(self):
        """Test successful retrieval of forest root DN."""
        action = configured_action()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "attributes": {"rootDomainNamingContext": ["DC=corp,DC=com"]},
            }
        ]

        action.client = mock_client
        result = action._get_forest_root_dn("DC=lab,DC=corp,DC=com")

        assert result == "DC=corp,DC=com"
        mock_client.search.assert_called_once()

    def test_perform_search_success(self):
        """Test successful single domain search."""
        action = configured_action()

        mock_client = Mock()
        mock_client.response = [
            {
                "type": "searchResEntry",
                "dn": "CN=testuser,CN=Users,DC=child1,DC=corp,DC=com",
                "attributes": {"cn": "testuser", "userAccountControl": 512},
            }
        ]

        action.client = mock_client
        result = action._perform_search("(samaccountname=testuser)", "DC=child1,DC=corp,DC=com")

        assert len(result) == 1
        assert result[0][0] == "CN=testuser,CN=Users,DC=child1,DC=corp,DC=com"
        assert result[0][1] == 512

    def test_perform_search_failure_silent(self):
        """Test search failure handling with raise_on_error=False."""
        action = configured_action()

        mock_client = Mock()
        mock_client.search.side_effect = Exception("LDAP error")

        action.client = mock_client
        result = action._perform_search("(samaccountname=testuser)", "DC=corp,DC=com", raise_on_error=False)

        assert result == []

    def test_perform_search_raises_on_error(self):
        """Test that search raises exception when raise_on_error is True."""
        action = configured_action()

        mock_client = Mock()
        mock_client.search.side_effect = Exception("LDAP error")

        action.client = mock_client
        with pytest.raises(Exception) as exc_info:
            action._perform_search("(samaccountname=testuser)", "DC=corp,DC=com", raise_on_error=True)

        assert "LDAP search failed" in str(exc_info.value)

    def test_search_userdn_query_multi_domain_fallback(self):
        """Test user search falls back to child domains when not found in primary domain."""
        action = configured_action()

        mock_client = Mock()

        action.client = mock_client
        with patch.object(action, "_perform_search") as mock_perform:
            with patch.object(action, "_get_forest_root_dn", return_value="DC=corp,DC=com"):
                with patch.object(
                    action,
                    "_get_child_domains",
                    return_value=["DC=child1,DC=corp,DC=com"],
                ):
                    mock_perform.side_effect = [
                        [],
                        [["CN=testuser,CN=Users,DC=child1,DC=corp,DC=com", 512]],
                    ]

                    result = action.search_userdn_query(
                        "testuser",
                        "DC=corp,DC=com",
                        search_child_domains=True,
                    )

                    assert len(result) == 1
                    assert "DC=child1" in result[0][0]

    def test_search_userdn_query_no_multi_domain_search(self):
        """Test that multi-domain search can be disabled."""
        action = configured_action()

        mock_client = Mock()

        action.client = mock_client
        with patch.object(action, "_perform_search") as mock_perform:
            mock_perform.return_value = []

            result = action.search_userdn_query(
                "testuser",
                "DC=corp,DC=com",
                search_child_domains=False,
            )

            assert result == []
            assert mock_perform.call_count == 1
