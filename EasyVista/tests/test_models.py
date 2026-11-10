import pytest
from pydantic import ValidationError

from easyvista_modules.models import EasyVistaConfiguration, ViewRequestsIncidentsListArguments


@pytest.mark.parametrize("max_rows", [0, -1])
def test_list_page_size_must_be_positive(max_rows):
    with pytest.raises(ValidationError):
        ViewRequestsIncidentsListArguments(max_rows=max_rows)


@pytest.mark.parametrize("max_rows", [None, 1, 100])
def test_valid_list_page_size(max_rows):
    assert ViewRequestsIncidentsListArguments(max_rows=max_rows).max_rows == max_rows


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/path",
        "https://user:pass@example.org",
        "file:///tmp/test",
        "https://example.org?token=x",
        "https://example.org#frag",
        "https://",
    ],
)
def test_base_url_rejects_non_host_urls(url):
    with pytest.raises(ValidationError):
        EasyVistaConfiguration(base_url=url, tenant_id="00001")


@pytest.mark.parametrize("use_token", [True, False])
def test_configuration_rejects_plaintext_transport(use_token):
    with pytest.raises(ValidationError, match="base_url must use HTTPS"):
        EasyVistaConfiguration(
            base_url="http://easyvista.example",
            tenant_id="00001",
            use_token=use_token,
            token="fake-token",
            username="user",
            password="fake-password",
        )


@pytest.mark.parametrize("tenant_id", ["", " ", "\t\r\n", "\u2003"])
def test_configuration_rejects_empty_tenant(tenant_id):
    with pytest.raises(ValidationError):
        EasyVistaConfiguration(base_url="https://easyvista.example", tenant_id=tenant_id)


def test_configuration_preserves_tenant_leading_zeros():
    config = EasyVistaConfiguration(base_url="https://easyvista.example/", tenant_id="00001")
    assert config.tenant_id == "00001"
    assert config.base_url == "https://easyvista.example"
