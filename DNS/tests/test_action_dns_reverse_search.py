from unittest.mock import patch
import socket
from dns_modules.action_dns_reverse_search import DnsReverseSearchAction


def test_action_dns_reverse_search_success():
    action = DnsReverseSearchAction()
    arguments = {"ip_address": "8.8.8.8"}

    # On simule une réponse positive de socket.gethostbyaddr
    with patch("socket.gethostbyaddr") as mock_gethostbyaddr:
        mock_gethostbyaddr.return_value = ("dns.google", [], ["8.8.8.8"])

        result = action.run(arguments=arguments)

        assert result["hostname"] == "dns.google"
        assert result["error"] is None
        mock_gethostbyaddr.assert_called_once_with("8.8.8.8")


def test_action_dns_reverse_search_failure():
    action = DnsReverseSearchAction()
    arguments = {"ip_address": "1.1.1.1"}

    # On simule une erreur de résolution (socket.herror)
    with patch("socket.gethostbyaddr") as mock_gethostbyaddr:
        mock_gethostbyaddr.side_effect = socket.herror("Unknown host")

        result = action.run(arguments=arguments)

        assert result["hostname"] is None
        assert result["error"] == "Unknown host"
        mock_gethostbyaddr.assert_called_once_with("1.1.1.1")
