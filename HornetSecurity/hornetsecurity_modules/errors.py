class HornetSecurityError(Exception):
    """Base class for all Hornet Security exceptions."""

    pass


class HornetSecurityAPIError(HornetSecurityError):
    """Exception raised for errors in the Hornet Security API."""

    pass


class UnknownObjectIdError(HornetSecurityAPIError):
    """Exception raised when an unknown object ID is encountered."""

    def __init__(self, scope: str):
        super().__init__(f"Unknown object ID for scope {scope}")
        self.scope = scope


class InvalidObjectIdError(HornetSecurityAPIError):
    """Exception raised when an invalid object ID is encountered."""

    def __init__(self, object_id: str):
        super().__init__(f"Invalid object ID: {object_id}")
        self.object_id = object_id


class FailedEmailHeaderFetchError(HornetSecurityAPIError):
    """Exception raised when fetching the email header fails."""

    def __init__(self, object_id: int, es_mail_id: str):
        super().__init__(f"Failed to fetch email header for object ID {object_id} and email ID {es_mail_id}")
        self.object_id = object_id
        self.es_mail_id = es_mail_id
