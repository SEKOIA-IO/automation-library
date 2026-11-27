import pytest
from pydantic import ValidationError

from sophos_module.base import SophosConfiguration

CONFIGURATION = {
    "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
    "api_host": "https://api.central.sophos.com",
    "client_id": "my-id",
    "client_secret": "my-password",
}


def test_configuration_defaults_graphql_api_url():
    # module configurations created before the Fusion connector have no graphql_api_url
    assert SophosConfiguration(**CONFIGURATION).graphql_api_url == "https://api.taegis.sophos.com"


def test_configuration_custom_graphql_api_url():
    configuration = SophosConfiguration(**CONFIGURATION, graphql_api_url="https://graphql.example.com")
    assert configuration.graphql_api_url == "https://graphql.example.com"


@pytest.mark.parametrize("missing", ["oauth2_authorization_url", "api_host", "client_id", "client_secret"])
def test_configuration_required_fields(missing):
    with pytest.raises(ValidationError):
        SophosConfiguration(**{key: value for key, value in CONFIGURATION.items() if key != missing})


def test_client_secret_is_secret():
    schema = SophosConfiguration.model_json_schema()
    assert schema["properties"]["client_secret"]["secret"] is True
