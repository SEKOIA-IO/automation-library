import pytest

from polyswarm_modules.validators import invalid_domain_reason, invalid_imphash_reason, invalid_url_reason


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
