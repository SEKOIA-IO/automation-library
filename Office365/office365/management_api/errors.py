import re

TENANT_NOT_PROVISIONED_PATTERN = re.compile(r"Tenant \S+ does not exist", re.IGNORECASE)


class O365Exception(Exception):  # noqa: N818 - public name kept for backward compatibility
    pass


class ApplicationAuthenticationFailed(O365Exception):
    def __init__(self, msg, **kwargs):
        super().__init__(msg)
        self.context = kwargs


class ContextualizedO365Exception(O365Exception):
    def __init__(self, **kwargs):
        self.context = kwargs

    def __str__(self):
        return " ".join([f"{name}='{value}'" for name, value in self.context.items()])


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
    def is_tenant_not_provisioned(self) -> bool:
        """Whether Microsoft reports the tenant as unknown to the Management Activity API.

        The API returns `Tenant <id> does not exist` when unified audit logging is not
        enabled (or not provisioned yet) on the tenant, even though authentication succeeds.
        """
        return any(TENANT_NOT_PROVISIONED_PATTERN.search(str(error)) for error in self.failures.values())


class FailedToListO365Subscriptions(ContextualizedO365Exception):
    pass


class FailedToGetO365SubscriptionContents(ContextualizedO365Exception):
    pass


class FailedToGetO365AuditContent(ContextualizedO365Exception):
    pass


class SessionClosedError(O365Exception):
    """Raised when an Office365 API call is attempted on a closed aiohttp session."""

    pass
