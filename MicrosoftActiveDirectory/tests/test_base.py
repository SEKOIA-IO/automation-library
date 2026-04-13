import os
import pytest
import ssl
from unittest.mock import Mock, patch
from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.models.common_models import MicrosoftADConfiguration


class ConcreteMicrosoftADAction(MicrosoftADAction):
    def run(self, arguments):
        pass


class TestClientTlsConfiguration:
    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_without_ca_certificate_and_skip_tls_uses_cert_required(
        self, mock_tls, mock_server, mock_connection
    ):
        """Without ca_certificate and skip_tls_verify=False, CERT_REQUIRED is used."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=None,
            skip_tls_verify=False,
        )
        action.module = mock_module

        _ = action.client

        mock_tls.assert_called_once_with(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS)
        mock_server.assert_called_once_with(
            host="ldap.example.com",
            port=636,
            use_ssl=True,
            tls=mock_tls.return_value,
        )

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_with_skip_tls_verify_uses_cert_none(self, mock_tls, mock_server, mock_connection):
        """With skip_tls_verify=True, CERT_NONE is used."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=None,
            skip_tls_verify=True,
        )
        action.module = mock_module

        _ = action.client

        mock_tls.assert_called_once_with(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS)
        assert mock_server.call_args[1]["tls"] == mock_tls.return_value

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_with_ca_certificate_uses_cert_required(self, mock_tls, mock_server, mock_connection):
        """With ca_certificate provided, CERT_REQUIRED is used with the CA file."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        ca_cert_content = "-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJALa...\n-----END CERTIFICATE-----"
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=ca_cert_content,
        )
        action.module = mock_module

        _ = action.client

        mock_tls.assert_called_once()
        call_kwargs = mock_tls.call_args[1]
        assert call_kwargs["validate"] == ssl.CERT_REQUIRED
        assert "ca_certs_file" in call_kwargs
        assert call_kwargs["ca_certs_file"].endswith(".pem")

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_with_ca_certificate_cleans_up_temp_file(self, mock_tls, mock_server, mock_connection):
        """The temporary CA file is deleted after the connection is established."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        ca_cert_content = "-----BEGIN CERTIFICATE-----\nTEST_CERT_CONTENT\n-----END CERTIFICATE-----"
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=ca_cert_content,
        )
        action.module = mock_module

        _ = action.client

        call_kwargs = mock_tls.call_args[1]
        ca_file_path = call_kwargs["ca_certs_file"]
        assert not os.path.exists(ca_file_path), "Temporary CA file should be deleted after connection"

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_skip_tls_takes_precedence_over_ca_certificate(self, mock_tls, mock_server, mock_connection):
        """If both ca_certificate and skip_tls_verify are set, skip_tls_verify takes precedence."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        ca_cert_content = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----"
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=ca_cert_content,
            skip_tls_verify=True,
        )
        action.module = mock_module

        _ = action.client

        call_kwargs = mock_tls.call_args[1]
        assert call_kwargs["validate"] == ssl.CERT_NONE

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_server_configured_with_ssl_on_port_636(self, mock_tls, mock_server, mock_connection):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            skip_tls_verify=True,
        )
        action.module = mock_module

        _ = action.client

        mock_server.assert_called_once_with(
            host="ldap.example.com",
            port=636,
            use_ssl=True,
            tls=mock_tls.return_value,
        )

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_connection_uses_credentials(self, mock_tls, mock_server, mock_connection):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="secret_password",
        )
        action.module = mock_module

        _ = action.client

        mock_connection.assert_called_once_with(
            mock_server.return_value,
            auto_bind=True,
            user="admin@example.com",
            password="secret_password",
        )


class TestSearchUserdnQuery:
    def test_search_returns_empty_list_when_no_users_found(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
                "attributes": {
                    "cn": "Test User",
                    "mail": "test@example.com",
                    "userAccountControl": 512,
                },
            }
        ]
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

        result = action.search_userdn_query("testuser", "DC=example,DC=com")

        assert result == []

    def test_search_raises_exception_on_ldap_error(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.search.side_effect = Exception("Connection timeout")
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

        with pytest.raises(Exception) as exc_info:
            action.search_userdn_query("testuser", "DC=example,DC=com")

        assert "LDAP search failed" in str(exc_info.value)
        assert "Connection timeout" in str(exc_info.value)

    def test_search_builds_correct_filter(self):
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()

        mock_client = Mock()
        mock_client.response = []
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

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
        action.__dict__["ldap_client"] = mock_client  # inject into cached_property slot

        result = action.search_userdn_query("user", "DC=example,DC=com")

        assert len(result) == 2


class TestLDAPClientCoverage:
    """Additional tests to cover uncovered lines in ldap_client.py."""

    def test_log_fallback_is_callable(self):
        """LDAPClient.log() no-op fallback (line 16) — called directly."""
        from microsoft_ad.client.ldap_client import LDAPClient

        client = object.__new__(LDAPClient)
        # Should not raise and return None
        assert client.log("test message", level="info") is None

    @patch("microsoft_ad.client.ldap_client.Connection")
    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_client_tls_ciphers_forwarded_to_tls(self, mock_tls, mock_server, mock_connection):
        """tls_ciphers config is forwarded to Tls (line 32)."""
        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            tls_ciphers="HIGH:!aNULL",
        )
        action.module = mock_module

        _ = action.client

        call_kwargs = mock_tls.call_args[1]
        assert call_kwargs.get("ciphers") == "HIGH:!aNULL"

    def test_ca_cert_path_returns_none_when_no_certificate(self):
        """_ca_cert_path returns None when ca_certificate is not set (line 54)."""
        from microsoft_ad.client.ldap_client import LDAPClient

        client = object.__new__(LDAPClient)
        client.log = Mock()
        mock_module = Mock()
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=None,
        )
        client.module = mock_module

        result = client._ca_cert_path
        assert result is None

    @patch("microsoft_ad.client.ldap_client.Server")
    @patch("microsoft_ad.client.ldap_client.Tls")
    def test_ldap_client_cleans_up_temp_file_on_connection_failure(self, mock_tls, mock_server):
        """CA temp file is cleaned up even when Connection raises (lines 91-96)."""
        import tempfile

        action = object.__new__(ConcreteMicrosoftADAction)
        action.log = Mock()
        mock_module = Mock()
        ca_cert_content = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----"
        mock_module.configuration = MicrosoftADConfiguration(
            servername="ldap.example.com",
            admin_username="admin@example.com",
            admin_password="password",
            ca_certificate=ca_cert_content,
        )
        action.module = mock_module

        # Make Connection raise to trigger the exception path
        with patch("microsoft_ad.client.ldap_client.Connection", side_effect=RuntimeError("conn failed")):
            with pytest.raises(RuntimeError, match="conn failed"):
                _ = action.ldap_client

        # The temp CA file written by _ca_cert_path should have been cleaned up
        ca_path = action.__dict__.get("_ca_cert_path")
        if ca_path:
            assert not os.path.exists(ca_path), "Temp CA file should be deleted even on connection failure"
