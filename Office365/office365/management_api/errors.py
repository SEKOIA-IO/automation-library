"""Errors of the Office 365 Management Activity API.

Each error knows whether it needs an action from the customer (`is_actionable`) and how to fix it (`hint`),
so that the connector decides how to handle an error in a single place, with an actionable message.
"""

import re

TENANT_NOT_PROVISIONED_PATTERN = re.compile(r"Tenant \S+ does not exist", re.IGNORECASE)

# HTTP status codes that won't disappear without an action from the customer
ACTIONABLE_STATUS_CODES = {401, 403}

AUTHENTICATION_HINT = "Please check the client ID, client secret and tenant ID of the connector."
PERMISSION_HINT = (
    "Please check that the application has the ActivityFeed.Read permission "
    "on the Office 365 Management APIs, with admin consent granted."
)
TENANT_NOT_PROVISIONED_HINT = (
    "Microsoft reports that the tenant does not exist for the Office 365 Management Activity API. "
    "This usually means that unified audit logging is not enabled in Microsoft Purview, was enabled less than "
    "24 hours ago, or that the tenant has no Microsoft 365 license with auditing. Please enable auditing in "
    "Microsoft Purview and wait for it to be provisioned: the connector retries the activation, "
    "or restart it if it was stopped."
)
GENERIC_HINT = "Please check the error details in the connector logs."


class O365Exception(Exception):  # noqa: N818 - public name kept for backward compatibility
    @property
    def is_actionable(self) -> bool:
        """Whether the error needs an action from the customer, instead of disappearing on its own"""
        return False

    @property
    def hint(self) -> str:
        """How to fix the error"""
        return GENERIC_HINT


class ApplicationAuthenticationFailed(O365Exception):
    def __init__(self, msg, **kwargs):
        super().__init__(msg)
        self.context = kwargs

    @property
    def is_actionable(self) -> bool:
        return True

    @property
    def hint(self) -> str:
        response = self.context.get("response")
        if response and "error_description" in response:
            return f"{AUTHENTICATION_HINT} Details: {response['error_description']}"

        return AUTHENTICATION_HINT


class ContextualizedO365Exception(O365Exception):
    def __init__(self, **kwargs):
        self.context = kwargs

    def __str__(self):
        return " ".join([f"{name}='{value}'" for name, value in self.context.items()])

    @property
    def is_tenant_not_provisioned(self) -> bool:
        """Whether Microsoft reports the tenant as unknown to the Management Activity API.

        The API returns `Tenant <id> does not exist` when unified audit logging is not
        enabled (or not provisioned yet) on the tenant, even though authentication succeeds.
        """
        return TENANT_NOT_PROVISIONED_PATTERN.search(str(self)) is not None

    @property
    def is_actionable(self) -> bool:
        return self.context.get("status_code") in ACTIONABLE_STATUS_CODES or self.is_tenant_not_provisioned

    @property
    def hint(self) -> str:
        if self.is_tenant_not_provisioned:
            return TENANT_NOT_PROVISIONED_HINT

        if self.context.get("status_code") in ACTIONABLE_STATUS_CODES:
            return PERMISSION_HINT

        return GENERIC_HINT


class FailedToGetO365Token(ContextualizedO365Exception):
    pass


class FailedToActivateO365Subscription(ContextualizedO365Exception):
    pass


class FailedToActivateSomeO365Subscriptions(FailedToActivateO365Subscription):
    """Raised when at least one content type could not be activated.

    Each failing content type is tried independently, so the caller can tell
    whether some subscriptions are still active and events can still be collected.
    """

    def __init__(
        self,
        failures: dict[str, FailedToActivateO365Subscription],
        active_content_types: set[str],
    ):
        super().__init__(
            failed_content_types=sorted(failures),
            active_content_types=sorted(active_content_types),
        )
        self.failures = failures
        self.active_content_types = active_content_types

    def __str__(self):
        details = "; ".join(f"{content_type}: {error}" for content_type, error in sorted(self.failures.items()))
        return f"{super().__str__()} details=[{details}]"

    @property
    def is_actionable(self) -> bool:
        return any(error.is_actionable for error in self.failures.values())

    @property
    def hint(self) -> str:
        # the hint of the first failure that needs an action from the customer
        for _, error in sorted(self.failures.items()):
            if error.is_actionable:
                return error.hint

        return GENERIC_HINT


class FailedToListO365Subscriptions(ContextualizedO365Exception):
    pass


class FailedToGetO365SubscriptionContents(ContextualizedO365Exception):
    pass


class FailedToGetO365AuditContent(ContextualizedO365Exception):
    pass


class SessionClosedError(O365Exception):
    """Raised when an Office365 API call is attempted on a closed aiohttp session."""

    pass
