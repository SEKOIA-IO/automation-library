import pytest

from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
)


def test_application_authentication_failed_keeps_context():
    error = ApplicationAuthenticationFailed("Failed to get access token", response={"error": "invalid_client"})

    assert str(error) == "Failed to get access token"
    assert error.context == {"response": {"error": "invalid_client"}}


def test_contextualized_exception_str():
    error = FailedToActivateO365Subscription(content_type="Audit.General", status_code=400)

    assert str(error) == "content_type='Audit.General' status_code='400'"


@pytest.mark.parametrize(
    "error_message,expected",
    [
        pytest.param("Exception: DataServiceException: Tenant 2c126aec does not exist.", True, id="tenant_not_found"),
        pytest.param("tenant 2c126aec DOES NOT EXIST", True, id="case_insensitive"),
        pytest.param("The subscription is disabled.", False, id="other_error"),
    ],
)
def test_failed_to_activate_some_subscriptions_is_tenant_not_provisioned(error_message, expected):
    error = FailedToActivateSomeO365Subscriptions(
        failures={
            "Audit.Exchange": FailedToActivateO365Subscription(status_code=500),
            "Audit.General": FailedToActivateO365Subscription(error_code="AF10001", error_message=error_message),
        },
        active_content_types=set(),
    )

    assert error.is_tenant_not_provisioned is expected


def test_failed_to_activate_some_subscriptions_str():
    error = FailedToActivateSomeO365Subscriptions(
        failures={
            "Audit.General": FailedToActivateO365Subscription(content_type="Audit.General", status_code=400),
            "Audit.Exchange": FailedToActivateO365Subscription(content_type="Audit.Exchange", status_code=500),
        },
        active_content_types={"Audit.SharePoint"},
    )

    assert str(error) == (
        "failed_content_types='['Audit.Exchange', 'Audit.General']' active_content_types='['Audit.SharePoint']' "
        "details=[Audit.Exchange: content_type='Audit.Exchange' status_code='500'; "
        "Audit.General: content_type='Audit.General' status_code='400']"
    )
    assert isinstance(error, FailedToActivateO365Subscription)
