import pytest
from pydantic import ValidationError

from salesforce.models import SalesforceModuleConfig


@pytest.mark.parametrize(
    "configuration,expected_exception,validate_exception",
    [
        (
            {
                "client_secret": "secret",
                "client_id": "id",
                "base_url": "https://example.com",
                "org_type": "production",
                "rate_limit": "3/60",
            },
            None,
            None,
        ),
        (
            {
                "client_secret": "secret",
                "client_id": "id",
                "base_url": "example.com",
                "org_type": "production",
                "rate_limit": "3/60",
            },
            ValidationError,
            lambda exc_info: any(error["loc"] == ("base_url",) for error in exc_info.value.errors()),
        ),
    ],
)
def test_model_validation(configuration, expected_exception, validate_exception):
    """
    Test model validation.

    Args:
        configuration: dict
        expected_raise_exception: Exception
        validate_exception: Callable
    """
    if expected_exception:
        with pytest.raises(expected_exception) as exc_info:
            SalesforceModuleConfig(**configuration)
        if validate_exception and callable(validate_exception):
            assert validate_exception(exc_info)
    else:
        SalesforceModuleConfig(**configuration)
