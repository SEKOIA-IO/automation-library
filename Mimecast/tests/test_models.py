import pytest
from pydantic import ValidationError

from mimecast_modules.models import MimecastModuleConfiguration


def test_mimecast_module_configuration_valid() -> None:
    config = MimecastModuleConfiguration(client_id="id", client_secret="secret")

    assert config.client_id == "id"
    assert config.client_secret == "secret"


@pytest.mark.parametrize(
    "payload",
    [
        {"client_secret": "secret"},
        {"client_id": "id"},
        {},
    ],
)
def test_mimecast_module_configuration_requires_fields(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        MimecastModuleConfiguration(**payload)


def test_mimecast_module_configuration_schema_marks_secret() -> None:
    schema = MimecastModuleConfiguration.model_json_schema()
    secret_extra = schema["properties"]["client_secret"]["secret"]

    assert secret_extra is True
