import pytest

from salesforce.models import SalesforceModuleConfig


@pytest.mark.parametrize(
    "configuration,expected_raise_exception",
    [
        (
            {
                "client_secret": "secret",
                "client_id": "id",
                "base_url": "https://example.com",
                "org_type": "production",
                "rate_limit": "3/60",
            },
            False,
        ),
        (
            {
                "client_secret": "secret",
                "client_id": "id",
                "base_url": "example.com",
                "org_type": "production",
                "rate_limit": "3/60",
            },
            True,
        ),
    ],
)
def test_model_validation(configuration, expected_raise_exception):
    """
    Test model validation.

    Args:
        configuration: dict
        expected_raise_exception: bool
    """
    if expected_raise_exception:
        with pytest.raises(Exception):
            SalesforceModuleConfig(**configuration)
    else:
        SalesforceModuleConfig(**configuration)
