import pytest

from office365.management_api.errors import (
    AUTHENTICATION_HINT,
    GENERIC_HINT,
    PERMISSION_HINT,
    TENANT_NOT_PROVISIONED_HINT,
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
    O365Exception,
    SessionClosedError,
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


TENANT_NOT_FOUND_MESSAGE = "Exception: DataServiceException: Tenant 2c126aec does not exist."


@pytest.mark.parametrize(
    "error,expected_actionable,expected_hint",
    [
        pytest.param(O365Exception("boom"), False, GENERIC_HINT, id="base_error"),
        pytest.param(SessionClosedError("closed"), False, GENERIC_HINT, id="session_closed"),
        pytest.param(
            ApplicationAuthenticationFailed("Failed to get access token", response={"error": "invalid_client"}),
            True,
            AUTHENTICATION_HINT,
            id="authentication_failed",
        ),
        pytest.param(
            ApplicationAuthenticationFailed(
                "Failed to get access token", response={"error_description": "AADSTS7000215: Invalid client secret"}
            ),
            True,
            f"{AUTHENTICATION_HINT} Details: AADSTS7000215: Invalid client secret",
            id="authentication_failed_with_details",
        ),
        pytest.param(FailedToListO365Subscriptions(status_code=401), True, PERMISSION_HINT, id="listing_401"),
        pytest.param(FailedToGetO365AuditContent(status_code=403), True, PERMISSION_HINT, id="content_403"),
        pytest.param(FailedToGetO365SubscriptionContents(status_code=500), False, GENERIC_HINT, id="server_error"),
        pytest.param(
            FailedToListO365Subscriptions(error_message="ClientConnectionError: reset"),
            False,
            GENERIC_HINT,
            id="network_error",
        ),
        pytest.param(
            FailedToActivateO365Subscription(error_message=TENANT_NOT_FOUND_MESSAGE),
            True,
            TENANT_NOT_PROVISIONED_HINT,
            id="tenant_not_provisioned",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={
                    "Audit.Exchange": FailedToActivateO365Subscription(status_code=500),
                    "Audit.General": FailedToActivateO365Subscription(error_message=TENANT_NOT_FOUND_MESSAGE),
                },
                active_content_types=set(),
            ),
            True,
            TENANT_NOT_PROVISIONED_HINT,
            id="some_failures_with_an_actionable_one",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.Exchange": FailedToActivateO365Subscription(status_code=500)},
                active_content_types={"Audit.General"},
            ),
            False,
            GENERIC_HINT,
            id="some_failures_without_actionable_one",
        ),
    ],
)
def test_error_is_actionable_and_hint(error, expected_actionable, expected_hint):
    assert error.is_actionable is expected_actionable
    assert error.hint == expected_hint
