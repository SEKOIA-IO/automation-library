import socket
from unittest.mock import patch

from dns_modules.action_dns_reverse_search import DnsReverseSearchAction


def test_action_dns_reverse_search_success():
    action = DnsReverseSearchAction()
    arguments = {"ip_address": "8.8.8.8"}

    with patch("socket.gethostbyaddr") as mock_gethostbyaddr:
        mock_gethostbyaddr.return_value = ("dns.google", [], ["8.8.8.8"])

        result = action.run(arguments=arguments)

        assert result["hostname"] == "dns.google"
        assert result["error"] is None
        mock_gethostbyaddr.assert_called_once_with("8.8.8.8")


def test_action_dns_reverse_search_failure():
    action = DnsReverseSearchAction()
    arguments = {"ip_address": "1.1.1.1"}

    with patch("socket.gethostbyaddr") as mock_gethostbyaddr:
        mock_gethostbyaddr.side_effect = socket.herror("Unknown host")

        result = action.run(arguments=arguments)

        assert result["hostname"] is None
        assert result["error"] == "Unknown host"
        mock_gethostbyaddr.assert_called_once_with("1.1.1.1")


def test_action_dns_reverse_search_missing_ip():
    action = DnsReverseSearchAction()
    # Test du cas où l'argument ip_address est absent ou vide
    result = action.run(arguments={})

    assert "error" in result
    assert "Missing ip_address" in result["error"]


def test_action_dns_reverse_search_unexpected_exception():
    action = DnsReverseSearchAction()
    arguments = {"ip_address": "8.8.8.8"}

    # Test du bloc except Exception général
    with patch("socket.gethostbyaddr") as mock_gethostbyaddr:
        mock_gethostbyaddr.side_effect = Exception("Unexpected network failure")

        result = action.run(arguments=arguments)

        assert result["hostname"] is None
        assert "Unexpected network failure" in result["error"]
