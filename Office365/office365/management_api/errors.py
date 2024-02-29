class O365Exception(Exception):
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


class FailedToListO365Subscriptions(ContextualizedO365Exception):
    pass


class FailedToGetO365SubscriptionContents(ContextualizedO365Exception):
    pass


class FailedToGetO365AuditContent(ContextualizedO365Exception):
    pass
