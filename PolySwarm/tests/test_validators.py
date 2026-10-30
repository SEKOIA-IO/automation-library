import pytest

from polyswarm_modules.validators import (
    invalid_domain_reason,
    invalid_imphash_reason,
    invalid_url_reason,
    without_credentials,
)


@pytest.mark.parametrize(
    "name",
    ["printer.local", "nas.internal", "router.home.arpa", "app.localhost", "Printer.LOCAL", "printer.local."],
)
def test_a_name_refused_in_a_url_is_refused_as_a_domain(name: str) -> None:
    assert invalid_url_reason(f"http://{name}/") is not None
    reason = invalid_domain_reason(name)
    assert reason is not None
    assert "only exists inside a network" in reason


@pytest.mark.parametrize("name", ["example.com", "sub.example.co.uk", "locally.example.com", "example.local.com"])
def test_public_looking_domains_pass(name: str) -> None:
    assert invalid_domain_reason(name) is None


def test_the_ip_pointer_names_the_caller_supplied_action() -> None:
    reason = invalid_domain_reason("8.8.8.8", ip_action="SearchIp")
    assert reason is not None
    assert "SearchIp" in reason


@pytest.mark.parametrize("value", ["a" * 32, "A1" * 16, " " + "0f" * 16 + " "])
def test_an_imphash_is_32_hex_characters(value: str) -> None:
    assert invalid_imphash_reason(value) is None


@pytest.mark.parametrize("value", ["", "  ", "a" * 31, "a" * 33, "g" * 32, "a" * 40, "a" * 64])
def test_anything_else_is_not_an_imphash(value: str) -> None:
    assert invalid_imphash_reason(value) is not None


@pytest.mark.parametrize("name", ["127.1", "10.1.1", "0x7f.1", "192.168.001.001", "0x7f.0.0.1", "123.456"])
def test_short_form_ipv4_is_refused_as_a_domain(name: str) -> None:
    reason = invalid_domain_reason(name)

    assert reason is not None
    assert "ScanIp" in reason


@pytest.mark.parametrize("name", ["127.1", "10.1.1", "0x7f.1", "192.168.001.001"])
def test_short_form_ipv4_is_refused_in_a_url_too(name: str) -> None:
    assert invalid_url_reason(f"http://{name}/") is not None


@pytest.mark.parametrize(
    "name",
    ["123.example.com", "1e100.net", "a.1.example.org", "0x7f.example.com", "example.com", "999.999.example.com"],
)
def test_a_domain_with_a_numeric_label_is_still_accepted(name: str) -> None:
    assert invalid_domain_reason(name) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1\\@example.com/",
        "http://example.com\\@10.0.0.1/",
        "http://10.0.0.1\\example.com/",
    ],
)
def test_a_backslash_in_the_authority_is_refused(url: str) -> None:
    assert invalid_url_reason(url) is not None


@pytest.mark.parametrize(
    "url", ["http://user:secret@example.com/", "http://user@example.com/", "http://example.com:80@evil.example.org/"]
)
def test_a_credentialed_url_is_still_accepted_and_the_secret_is_never_reported(url: str) -> None:
    assert invalid_url_reason(url) is None
    assert "secret" not in without_credentials(url)


def test_a_credentialed_url_on_an_internal_host_is_refused_without_the_password() -> None:
    reason = invalid_url_reason("http://user:secret@10.0.0.1/")

    assert reason is not None
    assert "secret" not in reason


def test_a_url_the_two_parsers_read_differently_is_refused() -> None:
    from unittest.mock import patch

    with patch("polyswarm_modules.validators._whatwg_host", return_value="10.0.0.1"):
        reason = invalid_url_reason("http://example.com/")

    assert reason is not None
    assert "different host" in reason


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "https://sub.example.co.uk:8443/a?b=c#d",
        "http://example.com/a\\b",
        "http://example.com/path?email=a@b.com",
        "http://8.8.8.8/",
        "http://123.example.com/",
        "http://[2606:4700:4700::1111]:8080/x",
        "http://example.com./",
        "https://user:pw@sub.example.co.uk:8443/a?b=c@d#e",
    ],
)
def test_ordinary_urls_are_still_accepted(url: str) -> None:
    assert invalid_url_reason(url) is None
