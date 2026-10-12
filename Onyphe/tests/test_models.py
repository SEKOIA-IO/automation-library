import pytest
from pydantic import ValidationError

from onyphe.models import (
    OnypheDomainArguments,
    OnypheIPArguments,
    OnypheMD5Arguments,
    OnypheOnionArguments,
    OnyphePagedIPArguments,
)


def test_paged_ip_arguments_defaults():
    arguments = OnyphePagedIPArguments.model_validate({"ip": "2001:4860:4860:0:0:0:0:8888"})

    assert str(arguments.ip) == "2001:4860:4860::8888"
    assert arguments.budget == 1
    assert arguments.first_page == 1


def test_paging_arguments_accept_numeric_strings():
    arguments = OnyphePagedIPArguments.model_validate({"ip": "8.8.8.8", "budget": "0", "first_page": "2"})

    assert arguments.budget == 0
    assert arguments.first_page == 2


@pytest.mark.parametrize("ip", ["8.8.8", 8, " 8.8.8.8 ", "", None])
def test_ip_arguments_reject_invalid_ip(ip):
    with pytest.raises(ValidationError):
        OnypheIPArguments.model_validate({"ip": ip})


def test_domain_is_lowercased():
    assert OnypheDomainArguments.model_validate({"domain": "GOOGLE.COM"}).domain == "google.com"


def test_md5_is_lowercased():
    md5 = "D41D8CD98F00B204E9800998ECF8427E"

    assert OnypheMD5Arguments.model_validate({"md5": md5}).md5 == md5.lower()


def test_onion_is_lowercased():
    onion = "EXAMPLEEXAMPLE23.ONION"

    assert OnypheOnionArguments.model_validate({"onion": onion}).onion == onion.lower()


@pytest.mark.parametrize(
    "model, arguments",
    [
        (OnypheDomainArguments, {"domain": "a" * 250 + ".com"}),
        (OnypheDomainArguments, {"domain": ""}),
        (OnypheMD5Arguments, {"md5": "z" * 32}),
        (OnypheOnionArguments, {"onion": "example.onion"}),
    ],
)
def test_invalid_resource_is_rejected(model, arguments):
    with pytest.raises(ValidationError):
        model.model_validate(arguments)
